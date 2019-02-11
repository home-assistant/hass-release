"""Create the credits page for home-assistant.io."""
import re
import sys
import threading
import time
from collections import defaultdict
from queue import Queue

import pystache

from .const import (
    CREDITS_PAGE, CREDITS_TEMPLATE_FILE, GITHUB_ORGANIZATION_NAME,
    LOGIN_BY_EMAIL_FILE, NAME_BY_LOGIN_FILE, TOKEN_FILE)
from .github import MyGitHub

# TODO rewrite globals using partial?
# Dict structure:
# {
#     <user_login>: {
#         <repo_name>: <num_contributions_to_this_repo>,
#         <other_repo_name>: <num_contributions_to_other_repo>
#         ...
#     },
#     <other_user_login>: {
#         ...
#     }
#     ...
# }
org_contributors_dict = defaultdict(dict)
name_by_login = {}
login_by_email = {}
requests_tasks = Queue()  # Elements' type - RequestTask.
gh = None
default_per_page = 100


# TODO make RequestTasks construct URL by themselves
class RequestTask:
    """
    Base class for particular tasks. For each task, two actions must be
    performed:
    1. Access GitHub API to get corresponding data.
    2. Handle obtained data.
    """
    def __init__(self, url: str, **params):
        """
        :param url: API URL to be requested.
        :param params: Request's query string parameters.
        """
        self.url = url
        self.params = params
        self.response = None

    def handle(self):
        """Get data from the API."""
        self.response = gh.request_with_retry(self.url, self.params)

    def __repr__(self):
        """Represent the data."""
        return '{}\tresp: {}\turl:{}\tparams: {}'\
            .format(str(self.__class__).split('.')[-1][:-2],
                    'yes' if self.response is not None else 'None',
                    self.url, self.params)


class ReposPageTask(RequestTask):
    """A thread subclass to handle the repositories page."""

    def __init__(self, repos_page_url: str, **params):
        """Initialize the task."""
        super(ReposPageTask, self).__init__(repos_page_url, **params)

    def handle(self):
        """
        For each repo enqueue a ContributorsPageTask. If this repos page
        is not the last, enqueue an additional ReposPageTask for the next page.
        """
        super(ReposPageTask, self).handle()
        next_page_url_dict = self.response.links.get('next')
        if next_page_url_dict is not None:
            next_page_url = next_page_url_dict['url']
            new_task = ReposPageTask(next_page_url)
            requests_tasks.put(new_task)
        for repo in self.response.json():
            new_task = ContributorsPageTask(
                repo['contributors_url'], repo, anon='true',
                per_page=str(default_per_page))
            requests_tasks.put(new_task)


class ContributorsPageTask(RequestTask):
    """A thread subclass to handle the contributors pages."""

    def __init__(self, contributors_page_url: str, repo: dict, **params):
        """Initialize the task."""
        super().__init__(contributors_page_url, **params)
        self.repo = repo

    def handle(self):
        """Process contributors, list them in the org_contributors_dict.

        If this contributors page is not the last, enqueue a new
        ContributorsPageTask for the next page.
        """
        """
        According to https://developer.github.com/v3/repos/#list-contributors,
        "GitHub identifies contributors by author email address" and "only the
        first 500 author email addresses in the repository link to GitHub
        users. The rest will appear as anonymous contributors without
        associated GitHub user information".
        
        This means that we'll have to manually associate anonymous listed
        contributor entries with their GitHub accounts by email by searching
        commits.

        This also means that if the user has contributed to the repository 
        using several emails, the 'contributions' field of a retrieved
        non-anonymous user entry may not display the actual number of
        contributions this user made, and further in the list we may
        find anonymous entries, which must be also associated with this user.
        """
        super(ContributorsPageTask, self).handle()
        next_page_url_dict = self.response.links.get('next')
        if next_page_url_dict is not None:
            next_page_url = next_page_url_dict['url']
            new_task = ContributorsPageTask(next_page_url, self.repo)
            requests_tasks.put(new_task)
        for contr in self.response.json():
            if contr['type'] == 'User':
                if contr['login'] not in name_by_login:
                    # Requesting contributor's profile page to know his name.
                    new_task = ResolveNameByProfile(contr['url'])
                    requests_tasks.put(new_task)
                org_contributors_dict[contr['login']][self.repo['name']] = \
                    contr['contributions']
            # contr['type'] == 'Anonymous'
            else:
                login = login_by_email.get(contr['email'])
                if login is None:
                    # We could just get the login right from the email
                    # address, if it is '@users.noreply.github.com'-like,
                    # but we'll need to request the user name after that
                    # anyway.
                    # Retrieving contributor's login and name by a commit.
                    # repo['commits_url'] ends with '/commits{/sha}'.
                    # Removing the last 6.
                    commits_url = self.repo['commits_url'][:-6]
                    # Get contributor's login and name by a commit he made.
                    new_task = HandleAnonTask(commits_url, contr, self.repo)
                    requests_tasks.put(new_task)
                else:
                    contributions_already = \
                        org_contributors_dict[login].get(self.repo['name'])
                    if contributions_already is not None:
                        org_contributors_dict[login][self.repo['name']] = \
                            contr['contributions'] + contributions_already
                    else:
                        org_contributors_dict[login][self.repo['name']] = \
                            contr['contributions']


class ResolveNameByProfile(RequestTask):
    """A task to get user's name by accessing his GitHub profile."""

    def __init__(self, profile_url):
        """Initialize the resolver."""
        super(ResolveNameByProfile, self).__init__(profile_url)

    def handle(self):
        """
        Add user's name to the name_by_login dict. If the user has not
        specified his name, use the login as the name.
        """
        super(ResolveNameByProfile, self).handle()
        user = self.response.json()
        # If the user has not specified the name, use his login
        name_by_login[user['login']] = user['name'] or user['login']


class HandleAnonTask(RequestTask):
    """A task to handle an anonymous contributor entry."""
    def __init__(self, repo_commits_url: str, contributor: dict, repo: dict):
        super().__init__(repo_commits_url, author=contributor['email'],
                         per_page=1)
        self.contributor = contributor
        self.repo = repo

    def handle(self):
        """
        Add the contributor to the org_contributors_dict, if the user
        information can be retrieved, handle nothing otherwise.
        """
        super(HandleAnonTask, self).handle()
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
            # We can also get the user's name right from the commit.
            user_name = commit['commit']['author']['name']
            name_by_login[login] = user_name


class RequestsWorker(threading.Thread):
    """A thread subclass to handle the requests."""

    def run(self):
        """Run the requests worker."""
        time_to_retire = False
        while not time_to_retire:
            task = requests_tasks.get()
            # A None element will be put to the queue when the worker needs
            # to be terminated.
            if task is not None:
                task.handle()
            else:
                time_to_retire = True
            requests_tasks.task_done()


class ProgressReporter(threading.Thread):
    """A thread subclass used to monitor the execution progress."""

    def __init__(self, stop_monitoring: threading.Event,
                 report_period: float=5):
        """Initialize the reporter"""
        super(ProgressReporter, self).__init__()
        self.stop_monitoring = stop_monitoring
        self.report_period = report_period

    def run(self):
        """Run the progress reporter."""
        # Report every self.report_period seconds until the event is triggered.
        while not self.stop_monitoring.wait(self.report_period):
            print('name_by_login len: {}. org_contributors_dict len: {}'
                  .format(len(name_by_login), len(org_contributors_dict)))


def generate_credits(num_simul_requests, no_cache, quiet):
    """Authenticate to GitHub and collects the credits data."""
    global gh
    try:
        with open(TOKEN_FILE) as token_file:
            token = token_file.readline().strip()
        gh = MyGitHub(token)
    except OSError:
        sys.stderr.write('Could not open the .token file')
        print('Retrieving the data anonymously')
        gh = MyGitHub(token=None)
    gh.quiet = quiet
    global login_by_email
    global name_by_login

    def read_csv_to_dict(filename: str, encoding: str = None):
        """Read the CSV data into a dict."""
        data = {}
        with open(filename, encoding=encoding) as inp:
            for lin in inp:
                if ',' not in lin:
                    lin = lin.strip() + ','
                key, value = [val.strip() for val in lin.split(',')]
                data[key] = value
        return data
    if not no_cache:
        try:
            login_by_email = read_csv_to_dict(LOGIN_BY_EMAIL_FILE)
        except OSError:
            print('Could not read the login-by-email file. Proceeding without '
                  'the cache')
            login_by_email = {}
        try:
            name_by_login = read_csv_to_dict(
                NAME_BY_LOGIN_FILE, encoding='utf-8')
        except OSError:
            print('Could not read the name-by-login file. Proceeding without '
                  'the cache')
            name_by_login = {}
    else:
        login_by_email = {}
        name_by_login = {}
    # Test the API
    resp = gh.request_with_retry(MyGitHub.ENDPOINT)
    print('Status: {}. Message: {}. Rate-Limit remaining: {}'
          .format(resp.reason, resp.json().get('message'),
                  resp.headers.get(MyGitHub.RATELIMIT_REMAINING_STR)))
    request_workers = []

    for _ in range(0, num_simul_requests):
        new_thread = RequestsWorker()
        new_thread.start()
        request_workers.append(new_thread)
    org_repos_url = '{}/orgs/{}/repos'.format(
        MyGitHub.ENDPOINT, GITHUB_ORGANIZATION_NAME)
    new_task = ReposPageTask(org_repos_url, params={
        'type': 'public',
        'per_page': str(default_per_page)
    })
    requests_tasks.put(new_task)
    # RequestWorkers start working.
    if not quiet:
        all_done = threading.Event()
        reporter = ProgressReporter(all_done)
        reporter.start()
    requests_tasks.join()
    # Poisoning workers
    for _ in request_workers:
        requests_tasks.put(None)
    for worker in request_workers:
        worker.join()
    with open(NAME_BY_LOGIN_FILE, 'w', encoding='utf-8') as f:
        for login, name in name_by_login.items():
            f.write('{},{}\n'.format(login, name))
    with open(LOGIN_BY_EMAIL_FILE, 'w') as f:
        # TODO does it need to be sorted?
        for email, login in login_by_email.items():
            f.write('{},{}\n'.format(email, login))
    # Writing the credits page.
    users_context = {}
    for login, user_contribs_dict in org_contributors_dict.items():
        count_string = ''
        user_total_contribs = 0
        for repo_name, num_contribs in sorted(
                user_contribs_dict.items(), key=lambda x: x[1], reverse=True):
            count_string += '{} {} to {}\n'.format(
                num_contribs, 'commits' if num_contribs > 1 else 'commit',
                repo_name)
            user_total_contribs += num_contribs
        count_string = '{} total commits to the Home Assistant orga:\n{}'\
            .format(user_total_contribs, count_string)
        # TODO if the login_by_email file contains some users that
        # name_by_login file does not contain, (for example if it was modified
        # by 'hassrelease release-notes' run), a KeyError will occur here.
        name = name_by_login[login]
        name = re.sub(r'^(@)', r'', name)
        # TODO Mustache will escape these. Or will it?
        # name = name.replace('<', '&lt;')
        # name = name.replace('>', '&gt;')
        name = re.sub(r'([\\`*_{}[\]()#+-.!~|])', r'\\\1', name)
        users_context[login] = {
            'info': {
                'name': name,
                'login': login
            },
            'countString': count_string
        }
    fearless_leader = users_context.pop('balloob')
    context = {
        'allUsers': sorted(users_context.values(),
                           key=lambda x: x['info']['name'].casefold()),
        'fearlessLeader': fearless_leader,
        'headerDate': time.strftime('%Y-%m-%d, %X +0000', time.gmtime()),
        'footerDate': time.strftime('%A, %B %d %Y, %X UTC', time.gmtime()),
    }
    template_file = open(CREDITS_TEMPLATE_FILE, 'r')
    credits_page_file = open(CREDITS_PAGE, 'w', encoding='utf-8')
    credits_page_file.write(pystache.render(template_file.read(), context))
    template_file.close()
    credits_page_file.close()
    if not quiet:
        all_done.set()
        reporter.join()
