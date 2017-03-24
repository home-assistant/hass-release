from .github import get_session
from .model import Release, PRCache
from .changelog import generate


def main():
    github = get_session()
    repo = github.repository('home-assistant', 'home-assistant')
    release = Release('0.41')
    prs = PRCache(repo)

    generate(release, prs)


if __name__ == '__main__':
    main()
