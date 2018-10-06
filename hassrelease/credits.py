import subprocess
import sys


def generate_credits():
    process = subprocess.run(
        "node update_credits.js",
        shell=True,
        cwd="credits_generator"
    )
    if process.returncode != 0:
        sys.stderr.write("Error generating credits file\n")
        sys.exit(1)
