import os
import re
import pathlib

import click

from . import changelog
from . import credits as credits_module
from . import git, github, model, repo_core, repo_frontend
from .core import HassReleaseError
from .const import LABEL_CHERRY_PICKED
from .util import open_vscode


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

    print(
        f"PR link: https://github.com/home-assistant/home-assistant/compare/master...{branch}?expand=1&title={release}"
    )

    rel = model.Release(release, branch=branch)
    repo_root = pathlib.Path(__file__).parent.parent
    file_website = (repo_root / "data/{}.md".format(rel.identifier)).absolute()
    file_github = (repo_root / "data/{}-github.md".format(rel.identifier)).absolute()

    if force_update or not file_website.is_file():
        gh_session = github.get_session()
        repo = gh_session.repository("home-assistant", "home-assistant")
        prs = model.PRCache(repo)

        for file, website_tags in (file_website, True), (file_github, False):
            print("Writing", file)
            file.write_text(changelog.generate(rel, prs, website_tags=website_tags))
    else:
        print("Found existing files")
        print(file_website)
        print(file_github)

    open_vscode(file_website, file_github)


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
    docs_pr_ptrn = re.compile(r"home-assistant/home-assistant.github.io#(\d+)")
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
@click.option(
    "-f",
    "--feature-branch",
    is_flag=True,
    help="Allows to use the version of a feature branch of the frontend repo instead of the main branch",
)
@click.option(
    "-b",
    "--create-branch",
    is_flag=True,
    help="Create a new branch on the core repo, and push it to remote",
)
def bump_frontend(feature_branch, create_branch):
    if git.is_dirty(repo_core.PATH):
        print("Fatal error: the Home Assistant core repo has unstaged commits")
        return

    if not feature_branch and not git.is_main(repo_frontend.PATH):
        print(
            "Fatal error: the Frontend repo is not on the main branch, use `--feature-branch` to use the version of another branch"
        )
        return

    frontend = repo_frontend.get_version()

    branch_name = f"bump-frontend-{frontend}"

    if create_branch:
        git.create_branch(repo_core.PATH, branch_name)

    repo_core.update_frontend_version(frontend)
    repo_core.gen_requirements_all()
    repo_core.commit_all(f"Update frontend to {frontend}")

    if create_branch:
        print(
            f"PR link: https://github.com/home-assistant/home-assistant/compare/dev...{branch_name}?expand=1&title=Update%20frontend%20to%20{frontend}&body=https://github.com/home-assistant/frontend/releases/tag/{frontend}"
        )
        git.publish_branch(repo_core.PATH, branch_name)
        git.remove_branch(repo_core.PATH, branch_name)


@cli.command(help="Create new release post.")
def create_release_notes():
    # Create new file in io with correct date
    # Update _config.yml
    # Generate release notes and insert
    pass
