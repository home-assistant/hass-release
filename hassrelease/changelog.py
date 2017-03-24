from .users import update_users_with_release

OUTPUT = 'data/release-{}.md'
USER_TEMPLATE = '([@{0}])'
INFO_TEMPLATE = '([@{0}] - [#{1}])'
LINK_DEF_USER = '[@{0}]: https://github.com/{0}'
LINK_DEF_PR = '[#{0}]: https://github.com/home-assistant/home-assistant/pull/{0}'


def generate(release, prs):
    users = update_users_with_release(release, prs)

    breaking = []
    changes = []
    links = set()

    for line in release.log_lines():
        parts = [line.message]
        links.add(LINK_DEF_USER.format(users[line.email]))

        if line.pr is None:
            parts.append(USER_TEMPLATE.format(users[line.email]))
        else:
            parts.append(INFO_TEMPLATE.format(users[line.email], line.pr))
            links.add(LINK_DEF_PR.format(line.pr))

            for label in prs.get(line.pr).labels():
                if label.name == "breaking change":
                    breaking.append(line.pr)
                    parts.append("(Breaking Change)")

        changes.append(' '.join(parts))

    with open(OUTPUT.format(release.branch), 'wt') as outp:
        if breaking:
            outp.write('## Breaking changes\n\n')
            outp.write('\n'.join('- [#{}]'.format(pr) for pr in breaking))
            outp.write('\n\n')

        outp.write('## All changes\n\n')
        outp.write('\n'.join(changes))
        outp.write('\n\n')
        outp.write('\n'.join(sorted(links)))
        outp.write('\n')
