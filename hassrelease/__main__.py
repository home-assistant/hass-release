import click

from .commands import cli
from .core import HassReleaseError


def main(*args):
    try:
        cli()
    except HassReleaseError as err:
        click.secho('An error occurred: {}'.format(err), fg='red')


if __name__ == '__main__':
    main()
