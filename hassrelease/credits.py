import subprocess
import sys


def generate_credits():
    process = subprocess.run(
        'git show rc:homeassistant/const.py',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd='../home-assistant'
    )
    if process.returncode != 0:
        sys.stderr.write('Err\n')
    sys.stdout.write(
        str(process.returncode) + '\n\n' +
        str(process.stdout) + '\n\n' +
        str(process.stderr) + '\n\n'
    )