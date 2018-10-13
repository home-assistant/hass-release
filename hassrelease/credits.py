from .const import GITHUB_ORGANIZATION_NAME
from threading import Thread, Lock, Condition
from .github import MyGitHub
from .const import TOKEN_FILE
import sys
from queue import Queue
from urllib.parse import urlparse, parse_qs
from enum import Enum
from requests import Response


# Number of API requests the program is allowed to perform simultaneously.

def resolve_name_and_assign(
        contributor_record: ContributorData, contributor_profile_url: str):
    """
    Obtains a contributor's name from GitHub and writes it to an existing local
    contributor record.
    :param contributor_record: Whose name needs to be known.
    :param contributor_profile_url: Where to get the name from.
    :return:
    """
    user_response = request_with_retry(github_api_available_at,
                                       url=contributor_profile_url,
                                       headers=api_headers)
    user = user_response.json()
    # If the user has not specified the name, use his login
    contributor_record.name = user['name'] or user['login']


def resolve_anon_and_put_to_queue(repo: dict,
                                  contributor: dict,
                                  queue: Queue,
                                  ):
    """
    Resolves an anonymous contributor entry to a ContributorData class instance
    and puts it to a specified queue by accessing GitHub API.
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

    # TODO replace by users.py/resoolve_login
    """
    # repo['commits_url'] ends with '/commits{/sha}'.  Removing the last 6.
    commits_url = repo['commits_url'][:-6]
    # Remember, we only need one commit.
    commits_response = request_with_retry(
        available_since=github_api_available_at,
        url=commits_url,
        params={
            'author': contributor['email'],
            'per_page': 1
        },
        headers=api_headers)
    commit = commits_response.json()[0]
    # Check whether the email is linked to a GitHub profile.
    if commit['author'] is not None:
        contributor_login = commit['author']['login']
        # We can also get the user's name right from a commit.
        contributor_name = commit['commit']['author']['name']
        queue.put(ContributorData(
            login=contributor_login,
            name=contributor_name,
            num_contributions=contributor['contributions']))
    """
    # If this contributor is not linked to any GitHub account.
    # else:
    #     pass


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
    :param repo: A repo, whose contributors are being processed.
    :param page_num: The number of page to process.
    :param per_page: Number of contributors the API will return per page.
    :param repo_contributors_dict: A dict to which non-anonymous
    contributors must be written.
    :param anon_queue: A Queue to which initially-anonymous contributor
    entries must be added.
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
    # If we already have the page data.
    if page_data is not None:
        contributors = page_data
    else:
        contributors = request_with_retry(
            available_since=github_api_available_at,
            url=repo['contributors_url'],
            params={
                'anon': True,
                'per_page': per_page,
                'page': page_num
            },
            headers=api_headers
        ).json()
    for contributor in contributors:
        if contributor['type'] == 'User':
            # A non-anonymous contributor entry can only be seen once in
            # one repository, there's no need to check if the user is
            # already in the dictionary.
            contributor_record = ContributorData(
                login=contributor['login'],
                num_contributions=contributor['contributions'])
            repo_contributors_dict[contributor_record.login] = \
                contributor_record
            # User's name is not provided in contributor data entry.
            # We need to access GitHub user profile to obtain it. Requesting
            # it may take some time, creating a thread.
            user_thread = Thread(target=resolve_name_and_assign,
                                 args=(
                                     contributor_record,
                                     contributor['url']
                                 ))
            user_thread.start()
            non_anon_user_threads.append(user_thread)
        # If the contributor's data is anonymous (we only know his
        # email, name, and the number of contributions he made).
        else:
            # Gonna let another thread de-anonymize them, and then
            # put to a queue. We'll get back to them later.
            anon_user_thread = Thread(
                target=resolve_anon_and_put_to_queue,
                args=(
                    repo,
                    contributor,
                    anon_queue
                ))
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
                                                  ))


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
    # This means that we'll have to manually associate anonymous listed
    # contributor entries with their GitHub accounts by email by searching
    # commits.
    #
    # This also means that if the user has contributed to the repository using
    # several emails, the 'contributions' field of the retrieved
    # non-anonymous user entry may not display the actual number of
    # contributions this user made, and further in the list we may
    # find anonymous entries, which must be also associated with this user.

    # A queue that holds contributors, who were initially given by
    # GitHub as anonymous contributor entries.
    anon_queue = Queue()

    # First we're gonna have to know how many pages there are.
    per_page = 100
    contributors_first_page_resp = request_with_retry(
            available_since=github_api_available_at,
            url=repo['contributors_url'],
            params={
                'anon': True,
                'per_page': per_page,
            },
            headers=api_headers)
    # Get the last page number from the headers, if it is there.
    last_page_url_dict = contributors_first_page_resp.links.get('last')
    if last_page_url_dict is not None:
        last_page_url = last_page_url_dict['url']
        num_pages = int(parse_qs(urlparse(last_page_url).query)['page'][0])
    else:
        # All the content is provided in the current response.
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
    print('Done processing contributors "{}".'.format(repo['name']))

""""""



class TaskType(Enum):
    REPOS_PAGE = 1
    CONTRIBUTORS_PAGE = 2
    USER = 3
    COMMIT = 4


class RequestTask:
    def __init__(self, task_type: TaskType, url: str, params: dict=None,
                 data=None):
        self.type = task_type
        self.url = url
        self.params = params
        self.data = data


class HandleResponseTask:
    def __init__(self, task_type: TaskType, response: Response, data=None):
        self.type = task_type
        self.response = response
        self.data = data


class WipStatus:
    def __init__(self):
        self.working = False


def do_requests(request_tasks_q: Queue,
                handle_response_tasks_q: Queue,
                wip_status: WipStatus,
                new_work_or_done: Condition,
                gh: MyGitHub):
    """
    Takes tasks from request_tasks_q, requests what is said in it, puts a
    HandleResponseTask in the handle_response_tasks_q once it's done. Repeats.
    :param new_work_or_done:
    :param wip_status:
    :param request_tasks_q:
    :param handle_response_tasks_q:
    :param gh:
    :return:
    """
    while True:
        # Prevent queue changing.
        new_work_or_done.acquire()
        if request_tasks_q.empty():
            new_work_or_done.wait()
            if request_tasks_q.empty():
                # The thread is waken up, but there's no work.
                # This means that we're done.
                new_work_or_done.release()
                break
        request_tasks_q.get()
        wip_status.working = True
        new_work_or_done.release()
        rq_task = request_tasks_q.get()
        response = gh.request_with_retry(rq_task.url, rq_task.params)
        handle_response_tasks_q.put(HandleResponseTask(task_type=rq_task.type,
                                                       response=response))


def generate_credits(num_simul_requests):
    # Authenticate to GitHub. It is possible to receive required data as an
    # anonymous user.
    try:
        with open(TOKEN_FILE) as token_file:
            token = token_file.readline().strip()
        gh = MyGitHub(token)
    except OSError:
        sys.stderr.write('Could not open the .token file')
        print('Retrieving the data anonymously')
        gh = MyGitHub(token=None)
    # Test the API.
    resp = gh.request_with_retry(MyGitHub.ENDPOINT)
    print('Status: {}. Message: {}. Rate-Limit remaining: {}'
          .format(resp.reason, resp.json().get('message'),
                  resp.headers.get(MyGitHub.RATELIMIT_REMAINING_STR)))
    # Dict structure:
    # {
    #     <repository_name>: {
    #         <user_login>: <num_contributions_to_this_repo>
    #         ...
    #     }
    #     ...
    # }
    org_contributors_dict = {}
    name_by_login = {}  # TODO cache file input/output
    login_by_email = {}  # TODO cache file input/output
    request_tasks = Queue()  # Elements' type - RequestTask.
    handle_response_tasks = Queue()  # Elements' type - HandleResponseTask
    request_workers = []
    # A lock is associated with each worker. It is locked if the worker is
    # working, not waiting for a task.
    wip_statuses = []
    # Used to tell request_workers that there's a new request work to do. Or
    # if there's not gonna be any more.
    new_work_or_done = Condition()
    for _ in range(0, num_simul_requests):
        new_wip_status = WipStatus()
        wip_statuses.append(new_wip_status)
        new_thread = Thread(target=do_requests, args=(request_tasks,
                                                      handle_response_tasks,
                                                      new_wip_status,
                                                      new_work_or_done,
                                                      gh))
        new_thread.start()
        request_workers.append(new_thread)
    def add_rq_task_and_notify(task_type: TaskType, url: str,
                                    params: dict=None, data=None):
        with new_work_or_done:
            request_tasks.put(RequestTask(task_type, url, params, data))
    default_per_page = 100
    org_repos_url = '{}/orgs/{}/repos'.format(MyGitHub.ENDPOINT,
                                              GITHUB_ORGANIZATION_NAME)
    add_rq_task_and_notify(TaskType.REPOS_PAGE,
                                org_repos_url,
                                {'type': 'public',
                                 'per_page': default_per_page})

    done = False
    while not done:
        task = handle_response_tasks.get()
        if task.type == TaskType.REPOS_PAGE:
            next_page_url_dict = task.response.links.get('next')
            if next_page_url_dict is not None:
                next_page_url = next_page_url_dict['url']
                add_rq_task_and_notify(TaskType.REPOS_PAGE,
                                       next_page_url)
            for repo in task.response.json():
                org_contributors_dict[repo['name']] = {}
                add_rq_task_and_notify(TaskType.CONTRIBUTORS_PAGE,
                                       repo['contributors_url'],
                                       params={'anon': True,
                                               'per_page': default_per_page},
                                       data={'repo_name': repo['name']})
        elif task.type == TaskType.CONTRIBUTORS_PAGE:
            next_page_url_dict = task.response.links.get('next')
            if next_page_url_dict is not None:
                next_page_url = next_page_url_dict['url']
                add_rq_task_and_notify(TaskType.CONTRIBUTORS_PAGE,
                                       next_page_url,
                                       data=task.data)
            for contr in task.response.json():
                if contr['type'] == 'User':
                    # Requesting contributor's profile page to know his name.
                    add_rq_task_and_notify(task_type=TaskType.USER,
                                           url=contr['url'],
                                           data=contr['contributions'])
                    org_contributors_dict[]
        elif task.type == TaskType.ANON_USER:

        elif task.type == TaskType.NON_ANON_USER:




        # Hey, I see there's mo more works in the queue for y'all to take.
        if request_tasks.empty():
            # Are you guys done?
            for wip_status in wip_statuses:
                if wip_status.working:
                    # Oh ok. I'm gonna wait for you to finish.
                    break
            else:
                done = True
                with new_work_or_done:
                    # Wake every worker up while the request_tasks queue is
                    # empty.
                    new_work_or_done.notify_all()



    for worker in request_workers:
        worker.join()






    """"""
    next_repos_page_url = '{}/orgs/{}/repos'.format(ENDPOINT,
                                                    GITHUB_ORGANIZATION_NAME)
    # Do while there are pages left.
    while True:
        # Request the repositories list page.
        repos_resp = request_with_retry(
            available_since=github_api_available_at,
            url=next_repos_page_url,
            params={
                'type': 'public',
                'per_page': 100
            },
            headers=api_headers)
        print('Rate limit: ' + repos_resp.headers[RATELIMIT_REMAINING_STR] +
              '/' + repos_resp.headers[RATELIMIT_LIMIT_STR])
        repos = repos_resp.json()
        for repo in repos:
            # Create a new entry in the resulting dict for the current repo.
            curr_repo_dict = {}
            org_contributors_dict[repo['name']] = curr_repo_dict
            # Create a new thread, write it to the threads dict and start it.
            curr_thread = Thread(target=process_contributors_all,
                                 args=(repo, curr_repo_dict))
            curr_thread.start()
            repo_threads.append(curr_thread)
        # 'None'  will be returned if there is no next page.
        next_repos_page_dict = repos_resp.links.get('next')
        if next_repos_page_dict is None:
            break
        else:
            next_repos_page_url = next_repos_page_dict['url']
    for repo_thread in repo_threads:
        repo_thread.join()
