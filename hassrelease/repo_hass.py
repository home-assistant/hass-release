"""Helper for the Home Assistant repository."""
from pathlib import Path
import json
import subprocess

PATH = Path(__file__).parent / '../../core/'


def update_frontend_version(value):
    """Update frontend requirement."""
    manifest_path = PATH / 'homeassistant/components/frontend/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['requirements'] = [f"home-assistant-frontend=={value}"]
    manifest_path.write_text(json.dumps(manifest, indent=2))


def gen_requirements_all():
    """Run gen_requirements_all.py."""
    subprocess.run('python3 -m script.gen_requirements_all', cwd=PATH, shell=True)


def commit_all(message):
    """Commit all changed files."""
    subprocess.run(['git', 'commit', '-am', message], cwd=PATH)
