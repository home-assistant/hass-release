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


def test_blog_slug_major_release():
    """Test blog_slug for major releases without zero-padding."""
    release = Release("2026.4.0", branch="rc")
    assert release.blog_slug == "release-20264"
    
    release2 = Release("2026.12.0", branch="rc")
    assert release2.blog_slug == "release-202612"


def test_blog_slug_patch_release():
    """Test blog_slug for patch releases."""
    release = Release("2026.4.1", branch="rc")
    assert release.blog_slug == "release-202641"
    
    release2 = Release("2026.12.3", branch="rc")
    assert release2.blog_slug == "release-2026123"


def test_blog_date_components_major_release():
    """Test blog date components for major releases."""
    release = Release("2026.4.0", branch="rc")
    assert release.blog_year == 2026
    assert release.blog_month == 4
    assert release.blog_day == 1  # Default to 1 for major releases


def test_blog_date_components_patch_release():
    """Test blog date components for patch releases."""
    release = Release("2026.12.3", branch="rc")
    assert release.blog_year == 2026
    assert release.blog_month == 12
    assert release.blog_day == 3
