import os
import re

import click

from . import git, github, changelog, model
from .const import LABEL_CHERRY_PICKED
from .util import copy_clipboard


@click.group()
def cli():
    pass


@cli.command(help='Generate release notes for Home Assistant.')
@click.option('--branch', default='rc')
@click.option('--force-update/--no-force-update', default=False)
@click.option('--release', default=None)
def release_notes(branch, force_update, release):
    if release is None:
        release = git.get_hass_version(branch)
        print("Auto detected version", release)

    rel = model.Release(release, branch=branch)
    file_website = 'data/{}.md'.format(rel.identifier)
    file_github = 'data/{}-github.md'.format(rel.identifier)

    if force_update or not os.path.isfile(file_website):
        gh_session = github.get_session()
        repo = gh_session.repository('home-assistant', 'home-assistant')
        prs = model.PRCache(repo)

        for file, website_tags in (file_website, True), (file_github, False):
            with open(file, 'wt') as outp:
                outp.write(changelog.generate(
                    rel, prs, website_tags=website_tags))

    input('Press enter to copy website changelog to clipboard')
    with open(file_website, 'rt') as file:
        copy_clipboard(file.read())

    input('Press enter to copy GitHub changelog to clipboard')
    with open(file_github, 'rt') as file:
        copy_clipboard(file.read())


@cli.command(help='Cherry pick all merged PRs into the current branch.')
@click.option('--remote-repository', default='home-assistant')
@click.option('--local-repository', default='../home-assistant')
@click.option('--milestone', default=None)
def milestone_cherry_pick(remote_repository, local_repository, milestone):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', remote_repository)

    if milestone is None:
        gh_milestone = github.get_latest_version_milestone(repo)
        print('No milestone passed in. Found', gh_milestone.title)
    else:
        gh_milestone = github.get_milestone_by_title(repo, milestone)

    git.fetch()

    to_pick = []

    for issue in sorted(
            repo.issues(milestone=gh_milestone.number, state='closed'),
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
        git.cherry_pick(pull.merge_commit_sha, local_repository)
        issue.add_labels(LABEL_CHERRY_PICKED)


@cli.command(help='Mark merged PRs as cherry picked and closes milestone.')
@click.option('--milestone', default=None)
def milestone_close(milestone):
    gh_session = github.get_session()
    repo = gh_session.repository('home-assistant', 'home-assistant')

    if milestone is None:
        gh_milestone = github.get_latest_version_milestone(repo)
        print('No milestone passed in. Found', gh_milestone.title)
    else:
        gh_milestone = github.get_milestone_by_title(repo, milestone)

    gh_milestone.update(state='closed')


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
