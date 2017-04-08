import click

from .github import get_session
from .model import Release, PRCache
from .changelog import generate


@click.group()
def cli():
    pass


@cli.command()
@click.argument('release')
def release_notes(release):
    github = get_session()
    repo = github.repository('home-assistant', 'home-assistant')
    release = Release(release)
    prs = PRCache(repo)
    generate(release, prs)
