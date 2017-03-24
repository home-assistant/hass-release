from distutils.version import StrictVersion
import re

from .git import get_log
from .const import GH_NO_EMAIL_SUFFIX


class LogLine:
    PR_PATTERN = re.compile('\(#(\d+)\)')

    def __init__(self, line):
        parts = line.split()

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
    def __init__(self, release):
        self.release = StrictVersion(release)
        self._log_lines = None

    @property
    def branch(self):
        if self.release.version[-1] == 0:
            return 'release-{}-{}'.format(*self.release.version[:2])
        else:
            return 'release-{}-{}-{}'.format(*self.release.version)

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
