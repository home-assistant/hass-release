#!/usr/bin/env python3
from .const import GH_NO_EMAIL_SUFFIX, USERS_FILE
from .github import MyGitHub
# TODO github3.py objects (pr, prs) and bare dicts (repo) are mixed here.


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


def resolve_login(login_by_email: dict, email: str, *, pr=None, prs=None,
                  ask_input=True, context=None, repo: dict=None,
                  gh: MyGitHub=None):
    """
    Tries to resolve the user's email to user's login, and add the pair to
    'login_by_email'. Returns True if it has been added. Returns False if it is
    already there or if it failed to resolve the login.
    :param login_by_email:
    :param email:
    :param pr:
    :param prs:
    :param ask_input:
    :param context:
    :param repo:
    :param gh: If repo parameter is given, this parameter must be provided too.
    :return:
    """

    if email in login_by_email:
        return False

    login = None

    if email.endswith(GH_NO_EMAIL_SUFFIX):
        # Strip off suffix
        userid_and_username = email[:email.index(GH_NO_EMAIL_SUFFIX)]
        # Emails are in format <userid>+<username>@suffix. Get username.
        login = userid_and_username.split('+', 1)[-1]

    elif pr is not None:
        # Find the user by PR.
        login = prs.get(pr).user.login
        print('Found {} for {} from PR #{}'.format(login, email, pr))

    elif repo is not None:
        # Find the user by a commit he made to this repo.
        # repo['commits_url'] ends with '/commits{/sha}'.  Removing the last 6.
        commits_url = repo['commits_url'][:-6]
        commits_response = gh.request_with_retry(
            url=commits_url,
            params={
                'author': email,
                'per_page': 1
            })
        commit = commits_response.json()[0]
        # Check whether the email is linked to a GitHub profile.
        if commit['author'] is not None:
            login = commit['author']['login']
            # We can also get the user's name right from a commit.

    if login is None:
        if ask_input:
            if context is not None:
                print('Context', context)
            login = input('GitHub username for {}: '.format(email))
        else:
            print('Not asking input for {}'.format(email))
            return False

    login_by_email[email] = login
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
            resolve_login(users, line.email, pr=line.pr,
                          prs=prs, ask_input=ask_input, context=line.line)
        except KeyboardInterrupt:
            ask_input = False

    for email, github in sorted(login_by_email.items()):
        if not github:
            resolve_login(users, email, ask_input=ask_input)

    added = len(login_by_email) - users_init_len
    if added > 0:
        print("Added {} users".format(added))
        write_login_by_email_file(login_by_email)  # TODO replace with append_to_csv()?
    else:
        print("Users up to date")

    return login_by_email
