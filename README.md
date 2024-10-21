# Home Assistant Release helpers

Some helper scripts to help to make a new release.

This repository needs to have the same parent directory as your checked out Home Assistant repository.

1. Create a [GitHub token](https://github.com/settings/tokens/new) with `public_repo` and `read:user` rights and write it to `.token` file in the repository directory.
2. Run `pip3 install -e .`  to install the dependencies.

The package is now installed. Run `hassrelease --help` for additional info. Run `hassrelease <command> --help` to get information about a particular command.
