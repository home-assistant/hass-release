import re
from distutils.version import StrictVersion

from .git import get_log


class LogLine:
    PR_PATTERN = re.compile(r"\(#(\d+)\)")

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

        self.message = " ".join(parts)


class PRCache:
    def __init__(self, repo):
        self.repo = repo
        self.cache = {}

    def get(self, pr):
        if pr not in self.cache:
            self.cache[pr] = self.repo.issue(pr)
        return self.cache[pr]


class Release:
    def __init__(self, version, *, branch):
        self.version = StrictVersion(version)
        self.branch = branch
        self._log_lines = None

        if self.version.version[-1] == 0 and not self.version.prerelease:
            vstring = "-".join(map(str, self.version.version[:2]))
        else:
            vstring = "-".join(map(str, self.version.version))
        self.identifier = "release-" + vstring

        if self.version.prerelease:
            pstring = "".join(map(str, self.version.prerelease))
            self.identifier = self.identifier + pstring

    @property
    def is_patch_release(self):
        """Return if this is a patch release or not.

        Patch release is when X in 0.0.X is not 0.
        """
        return self.version.version[-1] != 0

    def log_lines(self):
        if self._log_lines is None:
            self._log_lines = [LogLine(line) for line in get_log(self.branch)]
        return self._log_lines
