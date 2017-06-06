from hassrelease.changelog import automation_link, _process_doc_label


def test_automation_link():
    assert automation_link('automation.mqtt') == \
        '/docs/automation/trigger/#mqtt-trigger'

    assert automation_link('automation.homeassistant') == \
        '/docs/automation/trigger/#home-assistant-trigger'

    assert automation_link('automation.numeric_state') == \
        '/docs/automation/trigger/#numeric-state-trigger'


def test_process_doc_label():
    links = set()
    parts = []

    _process_doc_label('platform: light.hue', parts, links)

    assert parts[-1] == '([light.hue docs])'
    assert next(iter(links)).startswith('[light.hue docs]')
