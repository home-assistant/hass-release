from .const import GITHUB_ORGANIZATION_NAME
from threading import Thread, Condition
from .github import MyGitHub
from .const import TOKEN_FILE, LOGIN_BY_EMAIL_FILE, NAME_BY_LOGIN_FILE,\
    CREDITS_TEMPLATE_FILE, CREDITS_PAGE
from .users import read_csv_to_dict
import sys
from queue import Queue
from collections import defaultdict
import pystache
import time


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
org_contributors_dict = defaultdict(dict)
name_by_login = {}
login_by_email = {}
name_by_login_file = None
login_by_email_file = None
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
                if contr['login'] not in name_by_login:
                    # Requesting contributor's profile page to know his name.
                    new_task = ResolveNameByLoginTask(contr['url'], self.repo)
                    enqueue_request_task_and_notify_worker(new_task)
                org_contributors_dict[contr['login']][self.repo['name']] = \
                    contr['contributions']
            # contr['type'] == 'Anonymous'
            else:
                login = login_by_email.get(contr['email'])
                if login is None:
                    # Retrieving contributor's login and name by a commit.
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
                else:
                    contributions_already = \
                        org_contributors_dict[login].get(self.repo['name'])
                    if contributions_already is not None:
                        org_contributors_dict[login][self.repo['name']] = \
                            contr['contributions'] + contributions_already
                    else:
                        org_contributors_dict[login][self.repo['name']] = \
                            contr['contributions']


class ResolveNameByLoginTask(RequestTask):
    def __init__(self, url: str, repo: dict, params: dict=None):
        super().__init__(url, params)
        self.repo = repo

    def do(self):
        user = self.response.json()
        # If the user has not specified the name, use his login
        name_by_login[user['login']] = user['name'] or user['login']
        name_by_login_file.write(
            '{},{}\n'.format(user['login'], user['name'] or user['login']))


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
            login = commit['author']['login']
            contributions_already =\
                org_contributors_dict[login].get(self.repo['name'])
            if contributions_already is not None:
                org_contributors_dict[login][self.repo['name']] =\
                    self.contributor['contributions'] + contributions_already
            else:
                org_contributors_dict[login][self.repo['name']] =\
                    self.contributor['contributions']
            login_by_email[self.contributor['email']] = login
            login_by_email_file.write(
                '{},{}\n'.format(self.contributor['email'], login))
            # We can also get the user's name right from the commit.
            user_name = commit['commit']['author']['name']
            name_by_login[login] = user_name
            name_by_login_file.write('{},{}\n'.format(login, user_name))


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
    global login_by_email
    try:
        login_by_email = read_csv_to_dict(LOGIN_BY_EMAIL_FILE)
    except OSError:
        print('Could not read the login-by-email file. Proceeding without '
              'the cache.')
        login_by_email = {}
    global name_by_login
    try:
        name_by_login = read_csv_to_dict(NAME_BY_LOGIN_FILE, encoding='utf-8')
    except OSError:
        print('Could not read the name-by-login file. Proceeding without '
              'the cache.')
        name_by_login = {}
    global login_by_email_file
    global name_by_login_file
    if no_cache:
        login_by_email_file = open(LOGIN_BY_EMAIL_FILE, 'w')
        name_by_login_file = open(NAME_BY_LOGIN_FILE, 'w', encoding='utf-8')
    else:
        login_by_email_file = open(LOGIN_BY_EMAIL_FILE, 'a')
        name_by_login_file = open(NAME_BY_LOGIN_FILE, 'a', encoding='utf-8')
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
    name_by_login_file.close()
    login_by_email_file.close()
    # Writing the credits page.
    users_context = {}
    for login, user_contribs_dict in org_contributors_dict.items():
        count_string = ''
        user_total_contribs = 0
        for repo_name, num_contribs in sorted(user_contribs_dict.items(),
                                              key=lambda x: x[1],
                                              reverse=True):
            count_string += '{} {} to {}\n'.format(num_contribs,
                'commits' if num_contribs>1 else 'commit', repo_name)
            user_total_contribs += num_contribs
        count_string = '{} total commits to the home-assistant ' \
                       'organization:\n{}'.format(user_total_contribs,
                                                 count_string)
        # TODO change name regex?
        users_context[login] = {
            'info': {
                'name': name_by_login[login],
                'username': login
            },
            'countString': count_string
        }
    fearlessLeader = users_context.pop('balloob')
    context = {
        'allUsers': users_context.values(),
        'fearlessLeader': fearlessLeader,
        'headerDate': time.strftime('%Y-%m-%d, %X +0000', time.gmtime()),
        'footerDate': time.strftime('%A, %B %d %Y, %X UTC', time.gmtime()),
    }
    # TODO use the 'arrow' module for date and time? Necessary?
    template_file = open(CREDITS_TEMPLATE_FILE, 'r')
    credits_page_file = open(CREDITS_PAGE, 'w', encoding='utf-8')
    credits_page_file.write(pystache.render(template_file.read(), context))
    template_file.close()
    credits_page_file.close()
