import re

import click

from . import git, github, changelog, model
from .const import LABEL_CHERRY_PICKED


@click.group()
def cli():
    pass


@cli.command(help='Generate release notes for Home Assistant.')
@click.option('--branch', default='rc')
@click.option('--website-tags/--no-website-tags', default=True)
@click.argument('release')
def release_notes(branch, website_tags, release):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    release = model.Release(release, branch=branch)
    prs = model.PRCache(repo)
    changelog.generate(release, prs, website_tags=website_tags)


@cli.command(help='Cherry pick all merged PRs into the current branch.')
@click.argument('title')
def milestone_cherry_pick(title):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(repo, title)
    git.fetch()

    to_pick = []

    for issue in sorted(
            repo.issues(milestone=milestone.number, state='closed'),
            key=lambda issue: issue.number):
        pull = repo.pull_request(issue.number)

        if not pull.is_merged():
            print("Not merged yet:", pull.title)
            continue

        if any(label.name == LABEL_CHERRY_PICKED for label in issue.labels()):
            print("Already cherry picked:", pull.title)
            continue

        to_pick.append((pull, issue))

    for pull, issue in to_pick:
        print("Cherry picking {}: {}".format(
            pull.title, pull.merge_commit_sha))
        git.cherry_pick(pull.merge_commit_sha)
        issue.add_labels(LABEL_CHERRY_PICKED)


@cli.command(help='Mark merged PRs as cherry picked and closes milestone.')
@click.argument('title')
def milestone_close(title):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    milestone = github.get_milestone_by_title(repo, title)

    for issue in repo.issues(milestone=milestone.number, state='closed'):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            issue.add_labels(LABEL_CHERRY_PICKED)

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


@cli.command(help='Find unmerged documentation PRs.')
@click.option('--branch', default='rc')
@click.argument('release')
def unmerged_docs(branch, release):
    docs_pr_ptrn = re.compile('home-assistant/home-assistant.github.io#(\d+)')
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')
    docs_repo = gh_session.repository('home-assistant', 'home-assistant.github.io')
    release = model.Release(release, branch=branch)
    prs = model.PRCache(repo)
    doc_prs = model.PRCache(docs_repo)

    for line in release.log_lines():
        if line.pr is None:
            continue

        pr = prs.get(line.pr)
        match = docs_pr_ptrn.search(pr.body_text)
        if not match:
            continue

        docs_pr = doc_prs.get(match.groups()[0])

        if docs_pr.state == 'closed':
            continue

        print(pr.title)
        print(docs_pr.html_url)
        print()
