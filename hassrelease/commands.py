import click

from .github import get_session
from .model import Release, PRCache
from . import git, changelog


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
    changelog.generate(release, prs)


@cli.command()
@click.argument('title')
def milestone_cherry_pick(title):
    github = get_session()
    repo = github.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(title)
    git.fetch()

    for issue in repo.issues(milestone=milestone.number, state='closed'):
        pull = repo.pull_request(issue.number)

        print("Cherry picking {}: {}".format(
            pull.title, pull.merge_commit_sha))

        if pull.is_merged():
            git.cherry_pick(pull.merge_commit_sha)


@cli.command()
@click.argument('title')
def milestone_close(title):
    github = get_session()
    repo = github.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(title)
    git.fetch()

    for issue in repo.issues(milestone=milestone.number, state='closed'):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            issue.add_label('cherry-picked')

    milestone.update(state='closed')
