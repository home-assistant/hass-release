import subprocess

from .core import HassReleaseError


def get_hass_version(branch):
    """Get the HA version of a branch."""
    process = subprocess.run(
        "git show {branch}:homeassistant/const.py".format(branch=branch),
        shell=True,
        cwd="../core",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    if process.returncode != 0:
        text = (
            "Failed getting HASS version of branch - Does home-assistant repo exist at "
            "../core? - Does branch {} exist?".format(branch)
        )
        raise HassReleaseError(text)

    locals = {}
    exec(process.stdout, {}, locals)
    return locals["__version__"]


def get_log(branch):
    process = subprocess.run(
        "git log origin/master...{branch} "
        "--pretty=format:'- %s (%ae)' --reverse".format(branch=branch),
        shell=True,
        cwd="../core",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    if process.returncode != 0:
        text = (
            "Failed getting log - Does home-assistant repo exist at "
            "../core? - Does branch {} exist?".format(branch)
        )
        raise HassReleaseError(text)

    output = process.stdout.decode("utf-8")
    last = None

    for line in output.split("\n"):
        # Filter out duplicate lines (I don't git very well)
        if line == last:
            continue
        last = line
        yield line


def fetch(repo):
    process = subprocess.run("git fetch", shell=True, cwd=repo)

    if process.returncode != 0:
        text = (
            "Updating Home Assistant repo failed - Does home-assistant repo exist at "
            "../core?"
        )
        raise HassReleaseError(text)


def cherry_pick(sha, cwd="../core"):
    process = subprocess.run("git cherry-pick {}".format(sha), shell=True, cwd=cwd)

    if process.returncode != 0:
        text = (
            "Cherry picking {} failed - Does home-assistant repo exist at "
            "../core?".format(sha)
        )
        raise HassReleaseError(text)


def is_dirty(repo):
    """Test if repo is dirty."""
    return (
        subprocess.run(
            "git diff --stat", capture_output=True, shell=True, cwd=repo
        ).stdout
        != b""
    )


def is_main(repo):
    """Test if current repo is the main repo."""
    return (
        subprocess.run(
            "git branch --show-current", capture_output=True, shell=True, cwd=repo
        ).stdout
        == subprocess.run(
            "git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'",
            capture_output=True,
            shell=True,
            cwd=repo,
        ).stdout
    )


def create_branch(repo, branch):
    """Create a new branch on a repo."""
    process = subprocess.run(f"git checkout -b {branch}", shell=True, cwd=repo)

    if process.returncode != 0:
        raise HassReleaseError("Creating branch failed")


def publish_branch(repo, branch):
    """Publish a branch."""
    process = subprocess.run(f"git push -u origin {branch}", shell=True, cwd=repo)

    if process.returncode != 0:
        raise HassReleaseError("Publishing branch failed")


def remove_branch(repo, branch):
    """Remove a local branch."""
    default_branch = (
        subprocess.run(
            "git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'",
            capture_output=True,
            shell=True,
            cwd=repo,
        )
        .stdout.decode("UTF-8")
        .replace("\n", "")
    )

    process = subprocess.run(
        f"git checkout {default_branch} && git branch -d {branch}", shell=True, cwd=repo
    )

    if process.returncode != 0:
        raise HassReleaseError("Removing local branch failed")
