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


def automation_link(platform):
    """Return automation doc link."""
    if platform == 'automation.homeassistant':
        val = 'home-assistant'
    elif platform == 'automation.numeric_state':
        val = 'numeric-state'
    else:
        val = platform[len('automation.'):]

    return '[{} docs]: /docs/automation/trigger/#{}-trigger'.format(
        platform, val)


LABEL_MAP = {
    'discovery': None,
    'recorder': None,
    'automation.': automation_link,
    'emulated_hue.': None
}


def _process_doc_label(label, parts, links):
    """Process doc labels."""
    item = None

    for doc_label in DOCS_LABELS:
        if label.startswith(doc_label):
            item = label[len(doc_label):]
            break

    if not item:
        return

    part = DOC_TEMPLATE.format(item)
    link = LINK_DEF_DOC.format(item)

    for match, action in LABEL_MAP.items():
        if item.startswith(match):
            if action is None:
                # Ignore item completely
                return
            else:
                link = action(item)
            break

    parts.append(part)
    links.add(link)


def generate(release, prs):
    users = update_users_with_release(release, prs)

    label_groups = OrderedDict()
    label_groups['new-platform'] = []
    label_groups['new-feature'] = []
    label_groups['breaking change'] = []
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
            _process_doc_label(label, parts, links)

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
            if not prs:
                continue
            outp.write('## {}\n\n'.format(LABEL_HEADERS[label]))
            outp.write('\n'.join(prs))
            outp.write('\n\n')

        outp.write('## All changes\n\n')
        outp.write('\n'.join(changes))
        outp.write('\n\n')
        outp.write('\n'.join(sorted(links)))
        outp.write('\n')
