"""Helper for the Home Assistant repository."""
import os
import subprocess

PATH = os.path.join(os.path.dirname(__file__), '../../home-assistant/')


def update_frontend_version(value):
    """Update frontend requirement."""
    lines = []

    with open(os.path.join(
            PATH, 'homeassistant/components/frontend/manifest.json'), 'rt')\
            as setup_file:
        for line in setup_file:
            if 'home-assistant-frontend==' in line:
                lines.append(f'    "home-assistant-frontend=={value}"\n')
            else:
                lines.append(line)

    with open(os.path.join(
            PATH, 'homeassistant/components/frontend/manifest.json'), 'wt')\
            as init_file:
        init_file.writelines(lines)


def gen_requirements_all():
    """Run gen_requirements_all.py."""
    subprocess.run('script/gen_requirements_all.py', cwd=PATH)


def commit_all(message):
    """Commit all changed files."""
    subprocess.run(['git', 'commit', '-am', message], cwd=PATH)
