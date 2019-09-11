import subprocess
import sys

from .core import HassReleaseError


def get_hass_version(branch):
    """Get the HA version of a branch."""
    process = subprocess.run(
        "git show {branch}:homeassistant/const.py".format(branch=branch),
        shell=True,
        cwd="../home-assistant",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    if process.returncode != 0:
        text = (
            "Failed getting HASS version of branch - Does home-assistant repo exist at "
            "../home-assistant? - Does branch {} exist?".format(branch)
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
        cwd="../home-assistant",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    if process.returncode != 0:
        text = (
            "Failed getting log - Does home-assistant repo exist at "
            "../home-assistant? - Does branch {} exist?".format(branch)
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
            "../home-assistant?"
        )
        raise HassReleaseError(text)


def cherry_pick(sha, cwd="../home-assistant"):
    process = subprocess.run("git cherry-pick {}".format(sha), shell=True, cwd=cwd)

    if process.returncode != 0:
        text = (
            "Cherry picking {} failed - Does home-assistant repo exist at "
            "../home-assistant?".format(sha)
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
