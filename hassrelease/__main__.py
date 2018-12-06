import click

from .core import HassReleaseError
from .commands import cli


def main(*args):
    try:
        cli()
    except HassReleaseError as err:
        click.secho('An error occurred: {}'.format(err), fg='red')


if __name__ == '__main__':
    main()
