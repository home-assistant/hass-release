"""Helper for the Home Assistant frontend repository."""
import os

PATH = os.path.join(os.path.dirname(__file__), '../../frontend/')


def get_version():
    """Get current version of frontend repo."""
    found = None
    with open(os.path.join(PATH, 'setup.py'), 'rt') as setup_file:
        for line in setup_file:
            line = line.strip()
            if line.startswith('version='):
                found = line
                break

    if found is None:
        raise ValueError('Unable to detect version')

    return found.split('"')[-2]
