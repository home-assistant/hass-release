from distutils.version import StrictVersion
import re

from .git import get_log
from .const import GH_NO_EMAIL_SUFFIX


class LogLine:
    PR_PATTERN = re.compile('\(#(\d+)\)')

    def __init__(self, line):
        # Strip off the '-' at the start
        parts = line.split()[1:]

        self.line = line
        self.email = parts.pop()[1:-1]

        pr_match = self.PR_PATTERN.match(parts[-1])

        if pr_match:
            self.pr = int(pr_match.groups(1)[0])
            parts.pop()
        else:
            self.pr = None

        self.message = ' '.join(parts)


class PRCache:
    def __init__(self, repo):
        self.repo = repo
        self.cache = {}

    def get(self, pr):
        if pr not in self.cache:
            self.cache[pr] = self.repo.issue(pr)
        return self.cache[pr]


class Release:
    def __init__(self, version, *, branch=None):
        self.version = StrictVersion(version)
        self.version_raw = version
        self._log_lines = None

        if self.version.version[-1] == 0:
            self.identifier = 'release-{}-{}'.format(*self.version.version[:2])
        else:
            self.identifier = 'release-{}-{}-{}'.format(*self.version.version)


        if branch is not None:
            self.branch = branch
        elif self.version.version[-1] == 0:
            self.branch =  self.identifier

    def log_lines(self):
        if self._log_lines is None:
            self._log_lines = [LogLine(line) for line in get_log(self.branch)]
        return self._log_lines

    def discover_users(self, known_users, prs):
        users = {}

        for line in self.log_lines():
            email = line.email
            if email in known_users:
                github = known_users[email]
            elif email.endswith(GH_NO_EMAIL_SUFFIX):
                github = email[:email.index(GH_NO_EMAIL_SUFFIX)]
            elif line.pr is not None:
                github = prs.get(line.pr).login
                pass
            else:
                github = ''

            users[email] = github

        return users
