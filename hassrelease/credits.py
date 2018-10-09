from .const import GITHUB_ORGANIZATION_NAME
from threading import Thread, Semaphore
import requests
from .const import TOKEN_FILE
import sys
from queue import Queue, Empty
import time
from urllib.parse import urlparse, parse_qs


# Number of API requests the program is allowed to perform simultaneously.
NUM_SIMULTANEOUS_API_REQUESTS = 8
# A semaphore that controls number of simultaneous API requests.
api_semaphore = Semaphore(NUM_SIMULTANEOUS_API_REQUESTS)
# GitHub API endpoint address
ENDPOINT = 'https://api.github.com'
# GitHub API response header keys.
RATELIMIT_REMAINING_STR = 'X-RateLimit-Remaining'
RATELIMIT_LIMIT_STR = 'X-RateLimit-Limit'
RATELIMIT_RESET_STR = 'X-RateLimit-Reset'
RETRY_AFTER_STR = 'Retry-After'
# Additional headers for API requests.  For each request they're the same
# and contain the authorizations token. The token will be
# added later. It may not be added, the program will still proceed.
api_headers = {
    'Accept': 'application/vnd.github.v3+json'
}

# The time when the GitHub API is going to be available.
github_api_available_since = 0


class ContributorData:
    def __init__(self, login=None, name=None, num_contributions=0):
        self.login = login
        self.name = name
        self.num_contributions = num_contributions


def request_with_retry(available_since: int,
                       url: str,
                       params: dict=None,
                       **kwargs):
    """
    GETs HTTP data with awareness of possible rate-limit and rate-limit
    abuse protection limitations. If there are any, waits for them to
    expire and then retries.
    Basically a 'requests.get()' wrapper.
    :param available_since: The time when the resource is going to be available
    again after being unavailable (due to rate-limit exceeding or
    abuse-protection triggering).
    This variable is supposed to be shared between threads accessing the same
    resource in order to not prevent attempting to access it when it is
    unavailable.
    If this function receives a 'forbidden'-response, it changes this
    variable's value itself. We don't need a lock as long as we only assign
    values to it and especially as long as GIL is enabled.
    :param url: Matches the corresponding parameter of requests.get().
    :param params: Matches the corresponding parameter of requests.get().
    :param kwargs: Matches the corresponding parameter of requests.get().
    :return: Matches the return of requests.get() method.
    """
    with api_semaphore:  # TODO add semaphore comments
        # Retry until a response is returned.
        while True:
            # In how much seconds the API is going to be available?
            available_after = available_since - int(time.time())
            if available_after > 0:
                print('GitHub API is temporarily unavailable due to rate '
                      'limit restrictions. Retrying in {}s (at {})'
                      .format(available_after,
                              time.asctime(time.gmtime(time.time() +
                                                       available_after))))
                # TODO print
                # Wait for it to become available.
                time.sleep(available_after)
            # The API must be available at that point
            # Performing a request
            print('Requesting ' + url + ' ' + str(params))  # TODO
            resp = requests.get(url=url, params=params, **kwargs)
            # If forbidden (may be because of rate-limit timeout.  If so,
            # we'll wait and then retry).
            if resp.status_code == 403:
                # There may be multiple reasons for this.
                # If it is the rate-limit abuse protection, there will be such
                # field.
                retry_after = resp.headers.get(RETRY_AFTER_STR)
                # If it is the abuse protection.
                if retry_after is not None:
                    # Setting the 'available_since' according to the server
                    # response.
                    available_since = int(time.time()) + int(retry_after)
                    # Back to waiting.
                # If it is not the abuse protection.
                else:
                    # Maybe rate-limit exhaustion?
                    ratelimit_reset = resp.headers.get(RATELIMIT_RESET_STR)
                    # If it is rate-limit exhaustion.
                    if ratelimit_reset is not None:
                        # Set the 'available_since' according to the response.
                        available_since = int(ratelimit_reset)
                        # Back to waiting.
                    # If it is something else
                    else:
                        # This method is not responsible for this
                        return resp
            # If some other case. It may be a success, or it may be an another
            # error. Anyway this method is not responsible for this.
            else:
                return resp


def assign_contributor_name(
        contributor_record: ContributorData, contributor_profile_url: str):
    """
    Obtains a contributor's name from GitHub and writes it to an existing local
    contributor record.
    :param contributor_record: Whose name needs to be known.
    :param contributor_profile_url: Where to get the name from.
    :return:
    """
    user_response = request_with_retry(github_api_available_since,
                                       url=contributor_profile_url,
                                       headers=api_headers)
    user = user_response.json()
    # If the user has not specified the name, use his login
    contributor_record.name = user['name'] or user['login']


def resolve_anon_and_push_to_queue(repo: dict,
                                   contributor: dict,
                                   queue: Queue,
                                   ):
    """
    Resolves an anonymous contributor entry to a ContributorData class instance
    and pushes it to a specified queue by accessing GitHub API.
    :param contributor: The anonymous contributor that needs to be resolved
    :param queue: The queue where resolved users need to be put.
    :param repo: The repo to which the contributor contributed.
    :return:
    """
    # We can find a commit authored by this email's user and
    # extract his login from it, if it is there.  Otherwise this
    # email is not linked to any GitHub account.  There's also
    # an option to find an account by the user name (not login).
    # But names are not unique.

    # repo['commits_url'] ends with '/commits{/sha}'.  Removing
    # the last 6.
    # return  # TODO
    commits_url = repo['commits_url'][:-6]
    # Remember, we only need one commit.
    commits_response = request_with_retry(
        available_since=github_api_available_since,
        url=commits_url,
        params={
            'author': contributor['email'],
            'per_page': 1
        },
        headers=api_headers)
    # print('com_re:' + str(commits_response.json())) #TODO
    commit = commits_response.json()[0]
    # Check whether the email is linked to a GitHub profile.
    if commit['author'] is not None:
        contributor_login = commit['author']['login']
        # We can also get the user's name right from a commit.
        contributor_name = commit['commit']['author']['name']
        # Add the resolved user to the queue.
        queue.put(ContributorData(
            login=contributor_login,
            name=contributor_name,
            num_contributions=contributor['contributions']))
    # This contributor is not linked to any GitHub account.
    # else:


def process_contributors_one_page(repo: dict,
                                  page_num: int,
                                  per_page: int,
                                  repo_contributors_dict: dict,
                                  anon_queue: Queue,
                                  page_data: list = None):
    """
    Processes a specified page of the repo contributors list. Non-anonymous
    contributors are written to repo_contributors_dict, anonymous
    contributors are put into anon_queue.
    :param page_data: A contributors list. If specified, the API request is
    not performed and the data is taken from this list. Parameters 'repo',
    'page_num' and 'per_page' do not matter in that case.
    """
    # A list containing threads. Each thread obtains a
    # non-anonymous user's name (not login) by accessing the API.
    non_anon_user_threads = []
    # A list that holds threads which are responsible for resolving
    # anonymous entries to ContributorData class instances.
    anon_user_threads = []
    contributors_response = request_with_retry(
        available_since=github_api_available_since,
        url=repo['contributors_url'],
        params={
            'anon': True,
            'per_page': per_page,
            'page': page_num
        },
        headers=api_headers)
    contributors = contributors_response.json()
    for contributor in contributors:
        # print('contr_debug: ' + str(contributor))#TODO
        if contributor['type'] == 'User':
            # A non-anonymous contributor entry can only be seen once in
            # one repository, there's no need to check if the user is
            # already in the dictionary.
            # Add a new contributor's data structure to the dict.
            contributor_record = ContributorData(
                login=contributor['login'],
                num_contributions=contributor['contributions'])
            repo_contributors_dict[contributor['login']] = \
                contributor_record
            # User's name is not provided in contributor data entry.
            # We need to access GitHub user profile. Let's not wait and
            # give this job to another thread. He'll do fine, don't worry.
            user_thread = Thread(target=assign_contributor_name,
                                 args=(
                                     contributor_record,
                                     contributor['url']
                                 ))
            """assign_contributor_name(contributor_record, contributor['url'])"""
            # TODO threading
            user_thread.start()
            non_anon_user_threads.append(user_thread)
        # If the contributor's data is anonymous (we only know his
        # email, name, and the number of contributions he made).
        else:
            # print(contributor['email'] + ': ' + str(contributor[
            #    'contributions'])) # TODO
            # Gonna let another thread get de-anonymize them, and then
            # put to a queue. We'll get back to them later.
            anon_user_thread = Thread(
                target=resolve_anon_and_push_to_queue,
                args=(
                    repo,
                    contributor,
                    anon_queue
                ))
            """resolve_anon_and_push_to_queue(repo, contributor, anon_queue)"""
            # TODO threading
            anon_user_thread.start()
            anon_user_threads.append(anon_user_thread)
    # Jobs are given to everyone. Waiting for them to finish.
    for anon_user_thread in anon_user_threads:
        anon_user_thread.join()
    for user_thread in non_anon_user_threads:
        user_thread.join()
    print('Done processing contributors page {} repo {}. {} anons were '
          'enqueued so far. Non-anons: {}'.format(page_num, repo['name'],
                                                  anon_queue.qsize(),
                                                  len(repo_contributors_dict)
                                                  )) # TODO


def process_contributors_all(repo: dict,
                             repo_contributors_dict: dict):
    """
    Processes all the contributors to a specified repo and writes the result
    into repo_contributors_dict.
    :param repo: The repository to which contributions were made.
    :param repo_contributors_dict: An assumingly empty dictionary to which
    the resulting data needs to be output.  Has the following structure:
    {
        <user_login>: <ContributorData class instance>
        ...
    }
    :return:
    """
    # According to https://developer.github.com/v3/repos/#list-contributors,
    # "GitHub identifies contributors by author email address" and "only the
    # first 500 author email addresses in the repository link to GitHub
    # users. The rest will appear as anonymous contributors without
    # associated GitHub user information".
    #
    # This means that we'll have to manually associate anonymous listed_contributor
    # entries with their GitHub accounts by email by searching commits.
    #
    # This also means that if the user has contributed to the repository using
    # several emails, the 'contributions' field of the retrieved
    # non-anonymous user entry may not display the actual number of
    # contributions this user made, and further in the list we may
    # find anonymous entries, which must be also associated with this user.

    # A queue that hold ContributorData class instances that were given by
    # GitHub as anonymous listed_contributor entries.
    anon_queue = Queue()

    # First we're gonna have to know how many pages there are.
    per_page = 100
    contributors_first_page_resp = request_with_retry(
            available_since=github_api_available_since,
            url=repo['contributors_url'],
            params={
                'anon': True,
                'per_page': per_page,
            },
            headers=api_headers)
    # Get the last page number from the headers, if it is there.
    last_page_url_dict = contributors_first_page_resp.links.get('last')
    # If it is not there.
    if last_page_url_dict is not None:
        # We have the number of the last page.
        last_page_url = last_page_url_dict['url']
        # Get the last page number from the URL
        num_pages = int(parse_qs(urlparse(last_page_url).query)['page'][0])
    # That means that all the content is provided in the current response.
    else:
        num_pages = 1
    # Create an additional thread for each additional page. Already acquired
    # page (contributors_first_page_resp) will be processed by this thread.
    page_threads = []
    for page_num in range(2, num_pages + 1):
        new_thread = Thread(target=process_contributors_one_page,
                            args=(
                                repo,
                                page_num,
                                per_page,
                                repo_contributors_dict,
                                anon_queue
                            ))
        new_thread.start()
        page_threads.append(new_thread)
    # Process the first page by itself.
    process_contributors_one_page(repo, 1, per_page, repo_contributors_dict,
                                  anon_queue,
                                  contributors_first_page_resp.json())
    for page_thread in page_threads:
        page_thread.join()
    # All the contributors pages for this repository have been processed.
    # Initially-anonymous contributors are awaiting in the anon_queue.
    # As was said, if the user has committed to the repository using several
    # emails, he may have already been met in the list of contributors to
    # this repository.
    # Do-while the queue is not empty.
    while True:
        try:
            ex_anon = anon_queue.get_nowait()
        except Empty:
            break
        # Check whether the user is already listed.
        listed_contributor = repo_contributors_dict.get(ex_anon.login)
        # If the user is in already the dict.
        if listed_contributor is not None:
            # This means he used several emails. But the user is the same.
            # Incrementing his contributions counter.
            listed_contributor.num_contributions += ex_anon.num_contributions
        else:
            # Such user hasn't been listed yet. Adding him.
            repo_contributors_dict[ex_anon.login] = ex_anon
    print('Done processing contributors "{}".'.format(repo['name']))  #TODO


def generate_credits():
    # Authenticate to GitHub. It is possible to receive required data as an
    # anonymous user.
    try:
        with open(TOKEN_FILE) as token_file:
            token = token_file.readline().strip()
        global api_headers
        api_headers['Authorization'] = 'token ' + token
        repos_response = request_with_retry(
            available_since=github_api_available_since,
            url=ENDPOINT,
            params={
                'per_page': 100
            },
            headers=api_headers)
        print('Authentication status: ' + repos_response.reason)
        if repos_response.status_code != 200:
            print('Authentication failed, proceeding anonymously')
    except OSError:
        sys.stderr.write('Could not open the .token file')
        print('Retrieving the data anonymously')
    # A dictionary that contains the data we're trying to get.  Has the
    # following structure:
    # {
    #     <repository_name>: {
    #         <user_login>: <ContributorData class instance>
    #         ...
    #     }
    #     ...
    # }
    credits_dict = {}
    # A dictionary holding threads.  Each thread processes one repository.
    repo_threads = []
    # Now we're gonna request the list of the repositories.  It may be
    # paginated, so we use a loop.
    # Pre-loop initialization.
    next_repos_page_url = ENDPOINT + '/orgs/' + GITHUB_ORGANIZATION_NAME + \
                      '/repos' + '?type=public'
    # A do-while loop.
    while True:
        # Request a repositories list page
        repos_response = request_with_retry(
            available_since=github_api_available_since,
            url=next_repos_page_url,
            params={
                'per_page': 100
            },
            headers=api_headers)
        print('Rate limit: ' + repos_response.headers[RATELIMIT_REMAINING_STR] +
              '/' + repos_response.headers[RATELIMIT_LIMIT_STR])
        repos = repos_response.json()
        for repo in repos:
            # Create a new entry in the resulting dict for the current repo.
            curr_repo_dict = {}
            credits_dict[repo['name']] = curr_repo_dict
            # Create a new thread, write it to the threads dict and start it.
            curr_thread = Thread(target=process_contributors_all,
                                 args=(repo, curr_repo_dict))


            """
            curr_thread.start()
            """
            process_contributors_all(repo, curr_repo_dict)
            #
            #
            #

            repo_threads.append(curr_thread)


        # 'None'  will be returned if there is no next page.
        next_repos_page_dict = repos_response.links.get('next')
        # Stop if there is no more pages left.
        if next_repos_page_dict is None:
            break
        else:
            next_repos_page_url = next_repos_page_dict['url']
    for repo_thread in repo_threads:
        repo_thread.join()
    1+1
