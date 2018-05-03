from collections import OrderedDict
from distutils.version import StrictVersion
import sys

from .users import update_users_with_release

OUTPUT = 'data/{}.md'
INFO_TEMPLATE = '([@{0}] - [#{1}])'
PR_TEMPLATE = '([#{0}])'
DOC_TEMPLATE = '([{0} docs])'
LINK_DEF_USER = '[@{0}]: https://github.com/{0}'
LINK_DEF_PR = '[#{0}]: https://github.com/home-assistant/home-assistant/pull/{0}'
GITHUB_LINK_DEF_DOC = '[{0} docs]: https://www.home-assistant.io/components/{0}/'
LINK_DEF_DOC = '[{0} docs]: /components/{0}/'
DOCS_LABELS = set(['platform: ', 'component: '])
IGNORE_LINE_LABELS = set(['reverted'])
LABEL_HEADERS = {
    'new-platform': 'New Platforms',
    'new-feature': 'New Features',
    'breaking change': 'Breaking Changes',
    'cherry-picked': 'Beta Fixes',
}
# Handle special cases. None values will be ignored.

WEBSITE_DIVIDER = """## {% linkable_title If you need help... %}

...don't hesitate to use our very active [forums](https://community.home-assistant.io/) or join us for a little [chat](https://discord.gg/c5DvZ4e). The release notes have comments enabled but it's preferred if you use the former communication channels. Thanks.

## {% linkable_title Reporting Issues %}

Experiencing issues introduced by this release? Please report them in our [issue tracker](https://github.com/home-assistant/home-assistant/issues). Make sure to fill in all fields of the issue template.

<!--more-->
"""


def automation_link(platform, website_tags):
    """Return automation doc link."""
    if platform == 'automation.homeassistant':
        val = 'home-assistant'
    elif platform == 'automation.numeric_state':
        val = 'numeric-state'
    else:
        val = platform[len('automation.'):]

    if website_tags:
        format = '[{} docs]: /docs/automation/trigger/#{}-trigger'
    else:
        format = '[{} docs]: https://www.home-assistant.io/docs/automation/trigger/#{}-trigger'

    return format.format(platform, val)


LABEL_MAP = {
    'discovery': None,
    'recorder': None,
    'automation.': automation_link,
    'emulated_hue.': None
}


def _process_doc_label(label, parts, links, website_tags):
    """Process doc labels."""
    item = None

    for doc_label in DOCS_LABELS:
        if label.startswith(doc_label):
            item = label[len(doc_label):]
            break

    if not item:
        return

    part = DOC_TEMPLATE.format(item)
    if website_tags:
        link = LINK_DEF_DOC.format(item)
    else:
        link = GITHUB_LINK_DEF_DOC.format(item)

    for match, action in LABEL_MAP.items():
        if item.startswith(match):
            if action is None:
                # Ignore item completely
                return
            else:
                link = action(item, website_tags)
            break

    parts.append(part)
    links.add(link)


def generate(release, prs, *, website_tags):
    """Generate a changelog.

    website_tags: boolean if we should include tags for home-assistant.io
    """
    users = update_users_with_release(release, prs)

    label_groups = OrderedDict()
    label_groups['new-platform'] = []
    label_groups['new-feature'] = []
    label_groups['breaking change'] = []
    if release.version.version[-1] == 0:
        # Only add 'beta fix' for 0-release
        label_groups['cherry-picked'] = []

    changes = []
    links = set()
    for line in release.log_lines():
        labels = []
        parts = ['-', line.message]

        if line.email not in users:
            print('Error! Found unresolved user', line.email)
            sys.exit(1)

        # Filter out git commits that are not merge commits
        if line.pr is None:
            continue

        pr = prs.get(line.pr)

        if (pr.milestone is not None and
                StrictVersion(pr.milestone.title) != release.version):
            continue

        labels = [label.name for label in pr.labels()]

        # Filter out commits for which the PR has one of the ignored labels
        if any(label in IGNORE_LINE_LABELS for label in labels):
            continue

        links.add(LINK_DEF_USER.format(users[line.email]))
        parts.append(INFO_TEMPLATE.format(users[line.email], line.pr))
        links.add(LINK_DEF_PR.format(line.pr))

        for label in labels:
            _process_doc_label(label, parts, links, website_tags)

        for label in labels:
            if label in label_groups:
                if label == 'cherry-picked':
                    parts.append("(beta fix)")
                else:
                    parts.append("({})".format(label))

        msg = ' '.join(parts)
        changes.append(msg)

        for label in labels:
            if label not in label_groups:
                continue
            label_groups[label].append(msg)

    with open(OUTPUT.format(release.identifier), 'wt') as outp:
        for label, prs in label_groups.items():
            if label == 'breaking change' and website_tags:
                outp.write(WEBSITE_DIVIDER)

            if not prs:
                continue

            if website_tags:
                outp.write(f'## {{% linkable_title {LABEL_HEADERS[label]} %}}\n\n')
            else:
                outp.write(f'## {LABEL_HEADERS[label]}\n\n')
            outp.write('\n'.join(prs))
            outp.write('\n\n')

        if website_tags:
            outp.write('## {% linkable_title All changes %}' + '\n\n')
        else:
            outp.write('## All changes\n\n')

        outp.write('\n'.join(changes))
        outp.write('\n\n')
        outp.write('\n'.join(sorted(links)))
        outp.write('\n')
