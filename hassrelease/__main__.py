from .commands import cli
from .monkeypatch import patch

if __name__ == '__main__':
    patch()
    cli()
