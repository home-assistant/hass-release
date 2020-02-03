from hassrelease.model import LogLine, Release


def test_logline_basic():
    line = LogLine("- Hello world (test@email.com)\n")

    assert line.message == "Hello world"
    assert line.email == "test@email.com"
    assert line.pr is None


def test_logline_with_pr():
    line = LogLine("- Hello world (#1234) (test@email.com)\n")

    assert line.message == "Hello world"
    assert line.email == "test@email.com"
    assert line.pr == 1234


def test_release_branch():
    release = Release("0.40.1", branch="rc")
    assert release.identifier == "release-0-40-1"
