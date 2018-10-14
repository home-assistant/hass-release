from .const import GITHUB_ORGANIZATION_NAME
from threading import Thread, Condition
from .github import MyGitHub
from .const import TOKEN_FILE
import sys
from queue import Queue


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
# Used to tell request_workers that there's a new request work to do. Or
# if there's not gonna be any more.
new_work_or_done = Condition()
gh = None
default_per_page = 100


class RequestTask:
    def __init__(self, url: str, params: dict=None):
        self.url = url
        self.params = params  # Request query string parameters.
        self.response = None

    def set_response(self):
        self.response = gh.request_with_retry(self.url, self.params)

    def do(self):
        pass

    def __repr__(self):
        return '{}\tresp: {}\turl:{}\tparams: {}'\
            .format(str(self.__class__).split('.')[-1][:-2],
                    'yes' if self.response is not None else 'None',
                    self.url, self.params)


def enqueue_request_task_and_notify_worker(task: RequestTask):
    with new_work_or_done:
        request_tasks.put(task)
        new_work_or_done.notify()


class ReposPageTask(RequestTask):
    def do(self):
        next_page_url_dict = self.response.links.get('next')
        if next_page_url_dict is not None:
            next_page_url = next_page_url_dict['url']
            new_task = ReposPageTask(next_page_url)
            enqueue_request_task_and_notify_worker(new_task)
        for repo in self.response.json():
            org_contributors_dict[repo['name']] = {}
            new_task = ContributorsPageTask(repo['contributors_url'],
                                            repo,
                                            params={
                                                'anon': True,
                                                'per_page': default_per_page
                                            })
            enqueue_request_task_and_notify_worker(new_task)


class ContributorsPageTask(RequestTask):
    def __init__(self, url: str, repo: dict, params: dict=None):
        super().__init__(url, params)
        self.repo = repo

    def do(self):
        next_page_url_dict = self.response.links.get('next')
        if next_page_url_dict is not None:
            next_page_url = next_page_url_dict['url']
            new_task = ContributorsPageTask(next_page_url, self.repo)
            enqueue_request_task_and_notify_worker(new_task)
        for contr in self.response.json():
            if contr['type'] == 'User':
                # TODO resolve through cache
                # Requesting contributor's profile page to know his name.
                new_task = ResolveNameByLoginTask(contr['url'], self.repo)
                enqueue_request_task_and_notify_worker(new_task)
                org_contributors_dict[self.repo['name']][contr['login']] = \
                    contr['contributions']
            # contr['type'] == 'Anonymous'
            else:
                # TODO resolve through cache
                # repo['commits_url'] ends with '/commits{/sha}'.
                # Removing the last 6.
                commits_url = self.repo['commits_url'][:-6]
                # Get contributor's login and name by a commit he made.
                new_task = HandleAnonTask(commits_url, contr, self.repo,
                                          params={
                                              'author': contr['email'],
                                              'per_page': 1
                                          })
                enqueue_request_task_and_notify_worker(new_task)


class ResolveNameByLoginTask(RequestTask):
    def __init__(self, url: str, repo: dict, params: dict=None):
        super().__init__(url, params)
        self.repo = repo

    def do(self):
        user = self.response.json()
        # If the user has not specified the name, use his login
        name_by_login[user['login']] = user['name'] or user['login']


class HandleAnonTask(RequestTask):
    def __init__(self, url: str, contributor: dict, repo: dict,
                 params: dict=None):
        super().__init__(url, params)
        self.contributor = contributor
        self.repo = repo

    def do(self):
        commit = self.response.json()[0]
        # Check whether the email is linked to a GitHub profile.
        if commit['author'] is not None:
            user_login = commit['author']['login']
            if user_login in org_contributors_dict[self.repo['name']]:
                org_contributors_dict[self.repo['name']][user_login] += \
                    self.contributor['contributions']
            else:
                org_contributors_dict[self.repo['name']][user_login] =\
                    self.contributor['contributions']
            login_by_email[self.contributor['email']] = user_login
            # We can also get the user's name right from the commit.
            user_name = commit['commit']['author']['name']
            name_by_login[user_login] = user_name


class WipStatus:
    def __init__(self):
        self.working = False


def do_requests(wip_status: WipStatus):
    """
    Takes tasks from request_tasks_q, requests what is said in it, puts a
    HandleResponseTask in the handle_response_tasks_q once it's done. Repeats.
    :param wip_status:
    :return:
    """
    while True:
        # Prevent queue changing.
        new_work_or_done.acquire()
        if request_tasks.empty():
            new_work_or_done.wait()
            if request_tasks.empty():
                # The thread is waken up, but there's no work.
                # This means that we're done.
                new_work_or_done.release()
                break
        rq_task = request_tasks.get()
        wip_status.working = True
        new_work_or_done.release()
        rq_task.set_response()
        handle_response_tasks.put(rq_task)
        wip_status.working = False


def generate_credits(num_simul_requests, no_cache):
    # Authenticate to GitHub. It is possible to receive required data as an
    # anonymous user.
    global gh
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
    request_workers = []
    # A lock is associated with each worker. It is locked if the worker is
    # working, not waiting for a task.
    wip_statuses = []
    for _ in range(0, num_simul_requests):
        new_wip_status = WipStatus()
        wip_statuses.append(new_wip_status)
        new_thread = Thread(target=do_requests, args=(new_wip_status,))
        new_thread.start()
        request_workers.append(new_thread)
    org_repos_url = '{}/orgs/{}/repos'.format(MyGitHub.ENDPOINT,
                                              GITHUB_ORGANIZATION_NAME)
    new_task = ReposPageTask(org_repos_url, params={
        'type': 'public',
        'per_page': default_per_page
    })
    enqueue_request_task_and_notify_worker(new_task)

    done = False
    while not done:
        task = handle_response_tasks.get()
        task.do()
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
                    # empty. They will see this and will terminate.
                    new_work_or_done.notify_all()
    for worker in request_workers:
        worker.join()
    print(org_contributors_dict)
