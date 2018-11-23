import os
import subprocess

PATH = os.path.join(os.path.dirname(__file__), '../../home-assistant/')


def update_frontend_version(value):
    """Update frontend requirement."""
    lines = []

    with open(os.path.join(PATH, 'homeassistant/components/frontend/__init__.py'), 'rt') as fp:
        for line in fp:
            if line.startswith('REQUIREMENTS ='):
                lines.append(f"REQUIREMENTS = ['home-assistant-frontend=={value}']\n")
            else:
                lines.append(line)

    with open(os.path.join(PATH, 'homeassistant/components/frontend/__init__.py'), 'wt') as fp:
        fp.writelines(lines)


def gen_requirements_all():
    """Run gen_requirements_all.py."""
    subprocess.run('script/gen_requirements_all.py', cwd=PATH)


def commit_all(message):
    """Commit all changed files."""
    subprocess.run(['git', 'commit', '-am', message], cwd=PATH)
