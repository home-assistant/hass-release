#!/usr/bin/env python3
USERS = 'users.csv'
NOTES = 'notes.txt'
GH_NO_EMAIL_SUFFIX = '@users.noreply.github.com'
users = {}

with open(USERS) as inp:
    for lin in inp:
        if ',' not in lin:
            lin = lin.strip() + ','
        email, github = [val.strip() for val in lin.split(',')]
        users[email] = github

with open(NOTES) as inp:
    for lin in inp:
        email = lin.split()[-1][1:-1]
        if email not in users:
            users[email] = ''

require_username = len([val for val in users.values() if not val])

if require_username:
    print('Users requiring username: {}'.format(require_username))

to_write = []
require_write = False
ask_input = True

for email, github in sorted(users.items()):
    if not github and email.endswith(GH_NO_EMAIL_SUFFIX):
        github = users[email] = email[:email.index(GH_NO_EMAIL_SUFFIX)]
        require_write = True
        print('Auto detected username {} from {}'.format(github, email))
    elif not github and ask_input:
        try:
            github = users[email] = input(
                'GitHub username for {}: '.format(email))
            require_write = True
        except KeyboardInterrupt:
            ask_input = False

    to_write.append('{},{}'.format(email, github))

if require_write:
    with open(USERS, 'wt') as outp:
        outp.write('\n'.join(to_write))
