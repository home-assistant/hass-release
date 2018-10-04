import subprocess
import sys


def generate_credits():
    process = subprocess.run(
        "node update_credits.js",
        shell=True,
        # 'update_credits.js' has the following text in it:
        # 'fs.writeFile('../source/developers/credits.markdown
        # 'credits_generator' folder from home-assistant.io is going to be
        # removed, so we cd to another folder with the same level.
        cwd="credits_generator"
    )
    if process.returncode != 0:
        sys.stderr.write("Error generating credits file\n")
        sys.exit(1)
