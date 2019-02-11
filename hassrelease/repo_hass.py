"""Helper for the Home Assistant repository."""
import os
import subprocess

PATH = os.path.join(os.path.dirname(__file__), '../../home-assistant/')


def update_frontend_version(value):
    """Update frontend requirement."""
    lines = []

    with open(os.path.join(
            PATH, 'homeassistant/components/frontend/__init__.py'), 'rt')\
            as setup_file:
        for line in setup_file:
            if line.startswith('REQUIREMENTS ='):
                lines.append(f"REQUIREMENTS = ['home-assistant-frontend=="
                             f"{value}']\n")
            else:
                lines.append(line)

    with open(os.path.join(
            PATH, 'homeassistant/components/frontend/__init__.py'), 'wt')\
            as init_file:
        init_file.writelines(lines)


def gen_requirements_all():
    """Run gen_requirements_all.py."""
    subprocess.run('script/gen_requirements_all.py', cwd=PATH)


def commit_all(message):
    """Commit all changed files."""
    subprocess.run(['git', 'commit', '-am', message], cwd=PATH)
