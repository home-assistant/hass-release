import sys

from .github import get_session
from .model import Release, PRCache
from .changelog import generate


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(
            'No release specified. Please run '
            'python3 -m hassrelease <release>\n'.format(sys.argv[0]))
        sys.exit(1)

    github = get_session()
    repo = github.repository('home-assistant', 'home-assistant')
    release = Release(sys.argv[1])
    prs = PRCache(repo)

    generate(release, prs)


if __name__ == '__main__':
    main()
