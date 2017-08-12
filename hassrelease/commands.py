import click

from . import git, github, changelog, model


@click.group()
def cli():
    pass


@cli.command()
@click.argument('release')
def release_notes(release):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    release = model.Release(release)
    prs = model.PRCache(repo)
    changelog.generate(release, prs)


@cli.command()
@click.argument('title')
def milestone_cherry_pick(title):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(repo, title)
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
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(repo, title)
    git.fetch()

    for issue in repo.issues(milestone=milestone.number, state='closed'):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            issue.add_labels('cherry-picked')

    milestone.update(state='closed')
