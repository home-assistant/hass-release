from distutils.version import StrictVersion
import os
import sys
import time
import requests

from github3 import GitHub
from github3.exceptions import GitHubError

from .const import TOKEN_FILE


def get_session():
    """Fetch and/or load API authorization token for GITHUB."""
    if not os.path.isfile(TOKEN_FILE):
        sys.stderr.write('Please write a GitHub token to .token\n')
        sys.exit(1)

    with open(TOKEN_FILE) as fd:
        token = fd.readline().strip()

    gh = GitHub(token=token)
    try:  # Test connection before starting
        gh.is_starred('github', 'gitignore')
        return gh
    except GitHubError as exc:
        sys.stderr.write('Invalid token found\n')
        sys.exit(1)


def get_milestone_by_title(repo, title):
    """Fetch milestone by title."""
    seen = []
    for ms in repo.milestones(state='open'):
        if ms.title == title:
            return ms

        seen.append(ms.title)

    sys.stderr.write(
        'Milestone {} not found. Open milestones: {}\n'.format(
            title, ', '.join(seen)))
    sys.exit(1)


def get_latest_version_milestone(repo):
    """Fetch milestone by title."""
    milestones = []

    for ms in repo.milestones(state='open'):
        try:
            milestones.append((StrictVersion(ms.title), ms))
        except ValueError:
            print('Found milestone with invalid version', ms.title)

    if not milestones:
        sys.stderr.write('No milestones found\n')
        sys.exit(1)

    return list(reversed(sorted(milestones)))[0][1]


# TODO replace with a function? Use 'partial'.
class MyGitHub:
    # GitHub API endpoint address
    ENDPOINT = 'https://api.github.com'
    # GitHub API response header keys.
    RATELIMIT_REMAINING_STR = 'X-RateLimit-Remaining'
    RATELIMIT_LIMIT_STR = 'X-RateLimit-Limit'
    RATELIMIT_RESET_STR = 'X-RateLimit-Reset'
    RETRY_AFTER_STR = 'Retry-After'

    def __init__(self, token: str=None):
        # The time when the GitHub API is going to be available.
        self.next_time_available = 0
        self.last_logged_next_time_available = self.next_time_available
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if token is not None:
            self.headers['Authorization'] = 'token ' + token

    def log_timeout(self, available_after):
        if self.last_logged_next_time_available == self.next_time_available:
            pass
        else:
            print('Rate limit exceeded. Retrying in {} (at {})'
                  .format(time.strftime('%H:%M:%S',
                                        time.gmtime(available_after)),
                          time.asctime(time.gmtime(time.time() +
                                                   available_after))))
            self.last_logged_next_time_available = self.next_time_available

    def request_with_retry(self, url: str, params: dict=None):
        """
        GETs HTTP data with awareness of possible rate-limit and rate-limit
        abuse protection limitations. If there are any, waits for them to
        expire and then retries.
        Basically a 'requests.get()' wrapper.
        :param url: Matches the corresponding parameter of requests.get().
        :param params: Matches the corresponding parameter of requests.get().
        :return: Matches the return of requests.get() method.
        """
        # Retry until a response is returned.
        while True:
            available_after = self.next_time_available - int(time.time())
            if available_after > 0:
                self.log_timeout(available_after)
                time.sleep(available_after)
            # The API must be available at that point
            try:
                resp = requests.get(url, params, headers=self.headers)
            except requests.exceptions.ConnectionError as err:
                print('A ConnectionError was caught. Retrying. Error: {}'
                      .format(err))
                continue
            # If forbidden (may be because of rate-limit timeout.  If so,
            # we'll wait and then retry).
            if resp.status_code == 403:
                # There may be multiple reasons for this.
                # If it is the rate-limit abuse protection, there will
                # be such field.
                retry_after = resp.headers.get(MyGitHub.RETRY_AFTER_STR)
                if retry_after is not None:
                    self.next_time_available = int(time.time()) + int(
                        retry_after)
                    # Back to waiting.
                # If it is not the abuse protection.
                else:
                    # Maybe rate-limit exhaustion?
                    ratelimit_reset = resp.headers.get(
                        MyGitHub.RATELIMIT_RESET_STR)
                    # If it is rate-limit exhaustion.
                    if ratelimit_reset is not None:
                        self.next_time_available = int(ratelimit_reset)
                        # Back to waiting.
                    # If it is something else
                    else:
                        # This method is not responsible for this
                        return resp
            # If some other case. It may be a success, or it may be an
            # another error.  This method is not responsible for this.
            else:
                return resp
