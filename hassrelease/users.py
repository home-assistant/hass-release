#!/usr/bin/env python3
from .const import GH_NO_EMAIL_SUFFIX, USERS_FILE


def load_users():
    users = {}

    with open(USERS_FILE) as inp:
        for lin in inp:
            if ',' not in lin:
                lin = lin.strip() + ','
            email, github = [val.strip() for val in lin.split(',')]
            users[email] = github

    return users


def resolve_user(users, email, *, pr=None, prs=None, ask_input=True, context=None):
    """Resolves boolean if user added."""
    if email in users:
        return False

    github = None

    if email.endswith(GH_NO_EMAIL_SUFFIX):
        # Strip off suffix
        github = email[:email.index(GH_NO_EMAIL_SUFFIX)]
        # Emails are in format <userid>+<username>@suffix. Get username.
        github = github.split('+', 1)[-1]

    elif pr is not None:
        github = prs.get(pr).user.login
        print('Found {} for {} from PR #{}'.format(github, email, pr))

    if github is None:
        if ask_input:
            if context is not None:
                print('Context', context)
            github = input('GitHub username for {}: '.format(email))
        else:
            print('Not asking input for {}'.format(email))
            return False

    users[email] = github
    return True


def update_users_with_release(release, prs):
    users = load_users()

    added = 0
    ask_input = True

    for line in release.log_lines():
        try:
            if resolve_user(users, line.email, pr=line.pr,
                            prs=prs, ask_input=ask_input, context=line.line):
                added += 1
        except KeyboardInterrupt:
            ask_input = False

    for email, github in sorted(users.items()):
        if not github:
            if resolve_user(users, email, ask_input=ask_input):
                added += 1

    if added > 0:
        print("Added {} users".format(added))
        with open(USERS_FILE, 'wt') as outp:
            for email, github in sorted(users.items()):
                outp.write('{},{}\n'.format(email, github))
    else:
        print("Users up to date")

    return users
