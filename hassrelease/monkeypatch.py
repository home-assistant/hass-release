from github3.pulls import PullRequest


def patch():
    """Add a missing attribute to github3.py."""
    old_update = PullRequest._update_attributes

    def new_update(self, pull):
        self.merge_commit_sha = pull.get('merge_commit_sha')
        old_update(self, pull)

    PullRequest._update_attributes = new_update
