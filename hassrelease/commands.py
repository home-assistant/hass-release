import click

from . import git, github, changelog, model


@click.group()
def cli():
    pass


@cli.command(help='Generate release notes for Home Assistant.')
@click.argument('release')
def release_notes(release):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    release = model.Release(release)
    prs = model.PRCache(repo)
    changelog.generate(release, prs)


@cli.command(help='Cherry pick all merged PRs into the current branch.')
@click.argument('title')
def milestone_cherry_pick(title):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(repo, title)
    git.fetch()

    for issue in sorted(
            repo.issues(milestone=milestone.number, state='closed'),
            key=lambda issue: issue.number):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            print("Cherry picking {}: {}".format(
                pull.title, pull.merge_commit_sha))
            git.cherry_pick(pull.merge_commit_sha)


@cli.command(help='Mark merged PRs as cherry picked and closes milestone.')
@click.argument('title')
def milestone_close(title):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(repo, title)

    for issue in repo.issues(milestone=milestone.number, state='closed'):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            issue.add_labels('cherry-picked')

    milestone.update(state='closed')


@cli.command(help="List the merge commits of a milestone.")
@click.option('--repository', default='home-assistant')
@click.argument('title')
def milestone_list_commits(repository, title):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', repository)
    milestone = github.get_milestone_by_title(repo, title)

    commits = []

    for issue in sorted(
            repo.issues(milestone=milestone.number, state='closed'),
            key=lambda issue: issue.number):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            commits.append(pull.merge_commit_sha)

    print(' '.join(commits))
