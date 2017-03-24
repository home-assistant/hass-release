import subprocess
import sys


def get_log(branch):
    process = subprocess.run(
        "git log origin/master...origin/{branch} --no-merges "
        "--pretty=format:'- %s (%ae)' --reverse".format(branch=branch),
        shell=True,
        cwd='../home-assistant',
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    if process.returncode != 0:
        sys.stderr("Failed getting log")
        sys.stderr("Is home-assistant a git repo at ../home-assistant?")
        sys.stderr("Does branch {} exist?".format(branch))
        sys.exit(1)

    output = process.stdout.decode('utf-8')
    last = None

    for line in output.split('\n'):
        # Filter out duplicate lines (I don't git very well)
        if line == last:
            continue
        last = line
        yield line
