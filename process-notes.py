#!/usr/bin/env python3
import re

USERS = 'users.csv'
NOTES = 'notes.txt'
PROCESSED_NOTES = 'notes.md'
USER_TEMPLATE = '([@{0}])'
INFO_TEMPLATE = '([@{0}] - [#{1}])'
LINK_DEF_USER = '[@{0}]: https://github.com/{0}'
LINK_DEF_PR = '[#{0}]: https://github.com/home-assistant/home-assistant/pull/{0}'
PR_LINK_PATTERN = re.compile('\(#(\d+)\)')
users = {}


def parse_pr_link(text):
    match = PR_LINK_PATTERN.match(text)
    if match:
        return match.groups(1)[0]
    else:
        return None


def main():
    with open(USERS) as inp:
        for lin in inp:
            email, github = [val.strip() for val in lin.split(',')]
            users[email] = github

    to_write = []
    to_write_footer = set()

    with open(NOTES) as inp:
        for lin in inp:
            parts = lin.split()

            # We assume it's a PR if second to last part of the commit
            # matches (#1234)
            pr = parse_pr_link(parts[-2])
            if pr:
                to_write_footer.add(LINK_DEF_PR.format(pr))
                del parts[-2]

            email = parts[-1][1:-1]

            if email not in users:
                print("Found unknown user {}, "
                      "please run update-users.py".format(email))
                return

            if email in users:
                to_write_footer.add(LINK_DEF_USER.format(users[email]))
                if pr:
                    parts[-1] = INFO_TEMPLATE.format(users[email], pr)
                else:
                    parts[-1] = USER_TEMPLATE.format(users[email])

            to_write.append(' '.join(parts))

    with open(PROCESSED_NOTES, 'wt') as outp:
        outp.write('\n'.join(to_write))
        outp.write('\n\n')
        outp.write('\n'.join(sorted(to_write_footer)))
        outp.write('\n')

if __name__ == '__main__':
    main()
