#!/usr/bin/env python3
from .const import GH_NO_EMAIL_SUFFIX, USERS_FILE


def read_csv_to_dict(filename: str):
    data = {}
    with open(filename) as inp:
        for lin in inp:
            if ',' not in lin:
                lin = lin.strip() + ','
            key, value = [val.strip() for val in lin.split(',')]
            data[key] = value
    return data


def write_login_by_email_file(login_by_email_dict: dict):
    with open(USERS_FILE, 'wt') as outp:
        # TODO does it need to be sorted? Just use list(dict.items())?
        for email, github in sorted(login_by_email_dict.items()):
            outp.write('{},{}\n'.format(email, github))


def append_dict_to_csv(data: dict, filename: str):
    with open(filename, 'a') as file:
        for key, value in list(data.items()):
            file.write('{},{}\n'.format(key, value))


def resolve_login(users, email, *, pr=None, prs=None, ask_input=True, context=None):
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
    try:
        login_by_email = read_csv_to_dict(USERS_FILE)
    except FileNotFoundError:
        login_by_email = {}

    users_init_len = len(login_by_email)
    ask_input = True

    for line in release.log_lines():
        try:
            resolve_login(login_by_email, line.email, pr=line.pr,
                          prs=prs, ask_input=ask_input, context=line.line)
        except KeyboardInterrupt:
            ask_input = False

    for email, github in sorted(login_by_email.items()):
        if not github:
            resolve_login(login_by_email, email, ask_input=ask_input)

    added = len(login_by_email) - users_init_len
    if added > 0:
        print("Added {} users".format(added))
        write_login_by_email_file(login_by_email)  # TODO replace with append_to_csv()?
    else:
        print("Users up to date")

    return login_by_email
