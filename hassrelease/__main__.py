from .commands import cli
from .monkeypatch import patch

def main(*args):
    patch()
    cli()

if __name__ == '__main__':
    main()
