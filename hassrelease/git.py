import subprocess
import sys


def get_log(branch):
    process = subprocess.run(
        "git log origin/master...{branch} "
        "--pretty=format:'- %s (%ae)' --reverse".format(branch=branch),
        shell=True,
        cwd='../home-assistant',
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )

    if process.returncode != 0:
        sys.stderr.write("Failed getting log\n")
        sys.stderr.write(
            "Does home-assistant repo exist at ../home-assistant?\n")
        sys.stderr.write("Does branch {} exist?\n".format(branch))
        sys.exit(1)

    output = process.stdout.decode('utf-8')
    last = None

    for line in output.split('\n'):
        # Filter out duplicate lines (I don't git very well)
        if line == last:
            continue
        last = line
        yield line


def fetch():
    process = subprocess.run(
        "git fetch",
        shell=True,
        cwd='../home-assistant'
    )

    if process.returncode != 0:
        sys.stderr.write("Updating Home Assistant repo failed\n")
        sys.stderr.write(
            "Does home-assistant repo exist at ../home-assistant?\n")
        sys.exit(1)


def cherry_pick(sha, cwd='../home-assistant'):
    process = subprocess.run(
        "git cherry-pick {}".format(sha),
        shell=True,
        cwd=cwd
    )

    if process.returncode != 0:
        sys.stderr.write("Cherry picking {} failed\n".format(sha))
        sys.stderr.write(
            "Does home-assistant repo exist at ../home-assistant?\n")
        sys.exit(1)
