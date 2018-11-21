import os

PATH = os.path.join(os.path.dirname(__file__), '../../home-assistant-polymer/')


def get_version():
    """Get current version of frontend repo."""
    found = None
    with open(os.path.join(PATH, 'setup.py'), 'rt') as fp:
        for line in fp:
            line = line.strip()
            if line.startswith('version='):
                found = line
                break

    if found is None:
        raise ValueError('Unable to detect version')

    return found.split('"')[-2]

