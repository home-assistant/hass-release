from collections import OrderedDict

from .users import update_users_with_release

OUTPUT = 'data/release-{}.md'
USER_TEMPLATE = '([@{0}])'
INFO_TEMPLATE = '([@{0}] - [#{1}])'
PR_TEMPLATE = '([#{0}])'
LINK_DEF_USER = '[@{0}]: https://github.com/{0}'
LINK_DEF_PR = '[#{0}]: https://github.com/home-assistant/home-assistant/pull/{0}'


def generate(release, prs):
    users = update_users_with_release(release, prs)

    label_groups = OrderedDict()
    label_groups['new-platform'] = []
    label_groups['breaking change'] = []

    changes = []
    links = set()

    for line in release.log_lines():
        labels = []
        parts = ['-', line.message]
        links.add(LINK_DEF_USER.format(users[line.email]))

        if line.pr is None:
            parts.append(USER_TEMPLATE.format(users[line.email]))
        else:
            parts.append(INFO_TEMPLATE.format(users[line.email], line.pr))
            links.add(LINK_DEF_PR.format(line.pr))

            labels = [label.name for label in prs.get(line.pr).labels()]

        for label in labels:
            if label in label_groups:
                parts.append("({})".format(label))

        msg = ' '.join(parts)
        changes.append(msg)

        for label in labels:
            if label not in label_groups:
                continue
            label_groups[label].append(msg)

    with open(OUTPUT.format(release.branch), 'wt') as outp:
        for label, prs in label_groups.items():
            outp.write('## {}\n\n'.format(label))
            if prs:
                outp.write('\n'.join(prs))
            else:
                outp.write('None')
            outp.write('\n\n')

        outp.write('## All changes\n\n')
        outp.write('\n'.join(changes))
        outp.write('\n\n')
        outp.write('\n'.join(sorted(links)))
        outp.write('\n')
