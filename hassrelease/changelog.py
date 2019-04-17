from collections import OrderedDict
from datetime import datetime
from distutils.version import StrictVersion

INFO_TEMPLATE = '([@{0}] - [#{1}])'
PR_TEMPLATE = '([#{0}])'
DOC_TEMPLATE = '([{0} docs])'
LINK_DEF_USER = '[@{0}]: {1}'
LINK_DEF_PR = '[#{0}]: {1}'
GITHUB_LINK_DEF_DOC = '[{0} docs]: https://www.home-assistant.io/components/{0}/'
LINK_DEF_DOC = '[{0} docs]: /components/{0}/'
IGNORE_LINE_LABELS = set(['reverted'])
LABEL_HEADERS = {
    'new-integration': 'New Integrations',
    'new-platform': 'New Platforms',
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
    'discovery.': None,
    'recorder.': None,
    'automation.': automation_link,
    'emulated_hue.': None,
    'homeassistant.': None,
    'cloud.': lambda pl, _wt: f"[{pl} docs]: https://www.nabucasa.com/config/"
}


def _process_doc_label(label, parts, links, website_tags):
    """Process doc labels."""
    item = None

    if label.startswith('integration: '):
        item = label[len('integration: '):]

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
    label_groups = OrderedDict()
    label_groups['new-integration'] = []
    label_groups['new-platform'] = []
    label_groups['breaking change'] = []
    if release.version.version[-1] == 0:
        # Only add 'beta fix' for 0-release
        label_groups['cherry-picked'] = []

    changes = []
    links = set()
    for line in release.log_lines():
        parts = ['-', line.message]

        # Filter out git commits that are not merge commits
        if line.pr is None:
            continue

        pr = prs.get(line.pr)

        if (pr.milestone is not None and
            StrictVersion(pr.milestone.title).version !=
                release.version.version):  # Ignore beta version tag
            continue

        labels = [label.name for label in pr.labels()]

        # Filter out commits for which the PR has one of the ignored labels
        if any(label in IGNORE_LINE_LABELS for label in labels):
            continue

        user = pr.user
        links.add(LINK_DEF_USER.format(user.login, user.html_url))
        parts.append(INFO_TEMPLATE.format(user.login, pr.number))
        links.add(LINK_DEF_PR.format(pr.number, pr.html_url))

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

    outp = []

    if release.is_patch_release:
        if website_tags:
            now = datetime.now()
            outp.append(f'## {{% linkable_title Release {release.version} - {now.strftime("%B")} {now.day} %}}')
            outp.append('')

    else:
        for label, prs in label_groups.items():
            if label == 'breaking change' and website_tags:
                outp.append(WEBSITE_DIVIDER)

            if not prs:
                continue

            if website_tags:
                outp.append(f'## {{% linkable_title {LABEL_HEADERS[label]} %}}')
                outp.append('')
            else:
                outp.append(f'## {LABEL_HEADERS[label]}')
                outp.append('')
            outp.extend(prs)
            outp.append('')

        if website_tags:
            outp.append('## {% linkable_title All changes %}')
            outp.append('')
        else:
            outp.append('## All changes')
            outp.append('')

    outp.extend(changes)
    outp.append('')
    outp.extend(sorted(links))
    return '\n'.join(outp)
