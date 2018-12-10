from distutils.version import StrictVersion
import os

from github3 import GitHub
from github3.exceptions import GitHubError

from .core import HassReleaseError
from .const import TOKEN_FILE


def get_session():
    """Fetch and/or load API authorization token for GITHUB."""
    if not os.path.isfile(TOKEN_FILE):
        raise HassReleaseError('Please write a GitHub token to .token')

    with open(TOKEN_FILE) as fd:
        token = fd.readline().strip()

    gh = GitHub(token=token)
    try:  # Test connection before starting
        gh.is_starred('github', 'gitignore')
        return gh
    except GitHubError as exc:
        raise HassReleaseError('Invalid token found')


def get_milestone_by_title(repo, title):
    """Fetch milestone by title."""
    seen = []
    for ms in repo.milestones(state='open'):
        if ms.title == title:
            return ms

        seen.append(ms.title)

    raise HassReleaseError('Milestone {} not found. Open milestones: {}'.format(
                           title, ', '.join(seen)))


def get_latest_version_milestone(repo):
    """Fetch milestone by title."""
    milestones = []

    for ms in repo.milestones(state='open'):
        try:
            milestones.append((StrictVersion(ms.title), ms))
        except ValueError:
            print('Found milestone with invalid version', ms.title)

    if not milestones:
        raise HassReleaseError('No milestones found')

    return list(reversed(sorted(milestones)))[0][1]
