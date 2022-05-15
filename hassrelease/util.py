import subprocess


def copy_clipboard(text):
    """Copy text to the Mac clipboard."""
    subprocess.run("pbcopy", input=text.encode())


def open_vscode(*paths):
    """Open a file in VS Code."""
    subprocess.run(["code", *paths])


def prettier(path):
    """Run prettier on a file."""
    subprocess.run(["prettier", "--write", path])
