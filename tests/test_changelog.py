from hassrelease.changelog import automation_link, _process_doc_label


def test_automation_link():
    assert automation_link("automation.mqtt", False) == (
        "[automation.mqtt docs]: "
        "https://www.home-assistant.io/docs/automation/trigger/#mqtt-trigger"
    )

    assert automation_link("automation.homeassistant", False) == (
        "[automation.homeassistant docs]: "
        "https://www.home-assistant.io/docs/automation/trigger/"
        "#home-assistant-trigger"
    )

    assert automation_link("automation.numeric_state", False) == (
        "[automation.numeric_state docs]: "
        "https://www.home-assistant.io/docs/automation/trigger/"
        "#numeric-state-trigger"
    )


def test_process_doc_label():
    links = set()
    parts = []

    _process_doc_label("integration: hue", parts, links, False)

    assert parts[-1] == "([hue docs])"
    assert next(iter(links)).startswith("[hue docs]")
