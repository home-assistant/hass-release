import os
import re
import subprocess

import click

from . import changelog
from . import credits as credits_module
from . import git, github, model, repo_hass, repo_polymer
from .core import HassReleaseError
from .const import LABEL_CHERRY_PICKED
from .util import copy_clipboard


@click.group()
def cli():
    pass


@cli.command(help="Generate release notes for Home Assistant.")
@click.option("--branch", default="rc")
@click.option("--force-update/--no-force-update", default=False)
@click.option("--release", default=None)
def release_notes(branch, force_update, release):
    if release is None:
        release = git.get_hass_version(branch)
        print("Auto detected version", release)

    rel = model.Release(release, branch=branch)
    file_website = "data/{}.md".format(rel.identifier)
    file_github = "data/{}-github.md".format(rel.identifier)

    if force_update or not os.path.isfile(file_website):
        gh_session = github.get_session()
        repo = gh_session.repository("home-assistant", "home-assistant")
        prs = model.PRCache(repo)

        for file, website_tags in (file_website, True), (file_github, False):
            with open(file, "wt") as outp:
                outp.write(changelog.generate(rel, prs, website_tags=website_tags))

    input("Press enter to copy website changelog to clipboard")
    with open(file_website, "rt") as file:
        copy_clipboard(file.read())

    input("Press enter to copy GitHub changelog to clipboard")
    with open(file_github, "rt") as file:
        copy_clipboard(file.read())


@cli.command(help="Cherry pick all merged PRs into the current branch.")
@click.argument(
    "repo", default="hass", type=click.Choice(["hass", "docs", "frontend", "d", "f"])
)
@click.option("--milestone", default=None)
def pick(repo, milestone):
    if repo == "hass":
        remote_repository = "core"
    elif repo in ("f", "frontend"):
        remote_repository = "frontend"
    elif repo in ("d", "docs"):
        remote_repository = "home-assistant.io"

    print("Repository", remote_repository)

    local_repository = f"../{remote_repository}"
    gh_session = github.get_session()
    repo = gh_session.repository("home-assistant", remote_repository)

    if milestone is None:
        gh_milestone = github.get_latest_version_milestone(repo)
        print("No milestone passed in. Found", gh_milestone.title)
    else:
        gh_milestone = github.get_milestone_by_title(repo, milestone)

    git.fetch(local_repository)

    existing = []
    to_pick = []

    for issue in sorted(
        repo.issues(milestone=gh_milestone.number, state="closed"),
        key=lambda issue: issue.number,
    ):
        if not issue.pull_request_urls:
            continue

        existing.append(issue)

        if any(label.name == LABEL_CHERRY_PICKED for label in issue.labels()):
            print(f"Already cherry picked: {issue.title} (#{issue.number})")
            continue

        pull = repo.pull_request(issue.number)

        if not pull.is_merged():
            print("Not merged yet:", pull.title)
            continue


        existing.remove(issue)
        to_pick.append((pull, issue))

    print()

    failed_pick = None
    caught_err = None

    try:
        for pull, issue in to_pick:
            print(
                f"Cherry picking {pull.title} (https://www.github.com/home-assistant/{remote_repository}/pull/{pull.number})"
            )
            git.cherry_pick(pull.merge_commit_sha, local_repository)
            print()
            issue.add_labels(LABEL_CHERRY_PICKED)
    except HassReleaseError as err:
        failed_pick = pull
        caught_err = err


    print()
    print("Previously Picked")
    print()
    for issue in existing:
        print(f"- {issue.title} (@{issue.user.login} - #{issue.number})")
    print()
    print("Just Picked")
    print()
    for pull, _ in to_pick:
        if failed_pick is not None and failed_pick == pull:
            break
        print(f"- {pull.title} (@{pull.user.login} - #{pull.number})")

    if caught_err:
        print()
        raise caught_err


@cli.command(help="Mark merged PRs as cherry picked and closes milestone.")
@click.option("--milestone", default=None)
def milestone_close(milestone):
    gh_session = github.get_session()
    repo = gh_session.repository("home-assistant", "home-assistant")

    if milestone is None:
        gh_milestone = github.get_latest_version_milestone(repo)
        print("No milestone passed in. Found", gh_milestone.title)
    else:
        gh_milestone = github.get_milestone_by_title(repo, milestone)

    gh_milestone.update(state="closed")


@cli.command(help="List the merge commits of a milestone.")
@click.option("--repository", default="home-assistant")
@click.argument("title")
def milestone_list_commits(repository, title):
    gh_session = github.get_session()
    repo = gh_session.repository("home-assistant", repository)
    milestone = github.get_milestone_by_title(repo, title)

    commits = []

    for issue in sorted(
        repo.issues(milestone=milestone.number, state="closed"),
        key=lambda issue: issue.number,
    ):
        pull = repo.pull_request(issue.number)

        if pull.is_merged():
            commits.append(pull.merge_commit_sha)

    print(" ".join(commits))


@cli.command(help="Find unmerged documentation PRs.")
@click.option("--branch", default="rc")
@click.argument("release")
def unmerged_docs(branch, release):
    docs_pr_ptrn = re.compile("home-assistant/home-assistant.github.io#(\d+)")
    gh_session = github.get_session()
    repo = gh_session.repository("home-assistant", "home-assistant")
    docs_repo = gh_session.repository("home-assistant", "home-assistant.github.io")
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

        if docs_pr.state == "closed":
            continue

        print(pr.title)
        print(docs_pr.html_url)
        print()


@cli.command(
    help="Generate credits page"
    " (../home-assistant.io/source/developers/credits.markdown)"
)
@click.option(
    "-r",
    "--simul-requests",
    default=63,
    type=click.IntRange(min=1),
    show_default=True,
    help="Defines how many API requests can be " "performed simultaneously",
)
@click.option(
    "-c",
    "--no-cache",
    is_flag=True,
    help="Do not use the locally cached name-by-login and " "login-by-email files",
)
@click.option("-q", "--quiet", is_flag=True, help="Suppress console logging")
def credits(simul_requests, no_cache, quiet):
    credits_module.generate_credits(simul_requests, no_cache, quiet)


@cli.command(help="Bump frontend in hass.")
def bump_frontend():
    if git.is_dirty(repo_hass.PATH):
        print("Fatal error: the Home Assistant repo has unstaged commits")
        return

    frontend = repo_polymer.get_version()
    repo_hass.update_frontend_version(frontend)
    repo_hass.gen_requirements_all()
    repo_hass.commit_all(f"Updated frontend to {frontend}")


@cli.command(help="Create new release post.")
def create_release_notes():
    # Create new file in io with correct date
    # Update _config.yml
    # Generate release notes and insert
    pass
