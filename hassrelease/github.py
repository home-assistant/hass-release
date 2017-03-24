import os
import sys

from github3 import GitHub
from github3.exceptions import GitHubError

from .const import TOKEN_FILE


def get_session():
    """Fetch and/or load API authorization token for GITHUB."""
    if not os.path.isfile(TOKEN_FILE):
        sys.stderr('Please write a GitHub token to .token')
        sys.exit(1)

    with open(TOKEN_FILE) as fd:
        token = fd.readline().strip()

    gh = GitHub(token=token)
    try:  # Test connection before starting
        gh.is_starred('github', 'gitignore')
        return gh
    except GitHubError as exc:
        sys.stderr('Invalid token found')
        sys.exit(1)
