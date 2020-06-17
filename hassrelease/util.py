import subprocess


def copy_clipboard(text):
    """Copy text to the Mac clipboard."""
    subprocess.run("pbcopy", input=text.encode())
