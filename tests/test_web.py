import pytest

from helper import web
from helper.plugin_api import ACTIONS, TOPICS
from helper.widgets import WIDGETS


def test_every_built_in_component_is_valid_and_has_files():
    components = web.discover()
    assert {"drive", "clearance", "trade_here", "heading", "keys", "all_keys"} <= set(components)
    for component in components.values():
        assert component.files, component.name
        assert not any(file.endswith(".test.js") for file in component.files)
        assert all(topic in TOPICS for topic in component.topics)
        assert all(action in ACTIONS for action in component.actions)


def test_needs_are_loaded_first_and_once():
    components = web.discover()
    order = [c.name for c in web.loaded(components, ["all_keys", "keys"])]
    assert order == ["keys", "all_keys"]


def test_a_page_links_its_components_after_the_shared_files():
    page = web.page(web.discover(), ["trade_table"])
    lines = page.html.splitlines()
    scripts = [line for line in lines if line.startswith("<script")]
    assert scripts[:3] == [
        '<script src="dev.js"></script>',
        '<script src="widget.js"></script>',
        '<script src="../lib/dom.js"></script>',
    ]
    assert '<script src="../components/trade_table/trade_detail.js"></script>' in scripts
    assert page.topics == ("trade_rows", "trade_detail", "selection")
    assert "ui/open_commodity" in page.actions


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ('topics = ["secrets"]\n', "topics must be from"),
        ('topics = []\nactions = ["layout/move_widget"]\n', "actions must be from"),
        ("topics = []\ncolour = 1\n", "unknown settings: colour"),
    ],
)
def test_bad_component_files_say_whats_wrong(tmp_path, toml, message):
    (tmp_path / "lamp").mkdir()
    (tmp_path / "lamp" / "component.toml").write_text(toml)
    with pytest.raises(ValueError, match=message):
        web.discover(tmp_path)


def test_a_missing_need_is_reported(tmp_path):
    (tmp_path / "lamp").mkdir()
    (tmp_path / "lamp" / "component.toml").write_text('topics = []\nneeds = ["gone"]\n')
    with pytest.raises(ValueError, match="needs gone"):
        web.discover(tmp_path)


def test_every_component_has_named_states():
    assert all(component.states for component in web.discover().values())


def test_a_state_may_only_set_its_components_topics(tmp_path):
    (tmp_path / "lamp").mkdir()
    (tmp_path / "lamp" / "component.toml").write_text('topics = ["drive"]\n')
    (tmp_path / "lamp" / "lamp.states.json").write_text('{"odd": {"clearance": null}}')
    with pytest.raises(ValueError, match="may only set its topics"):
        web.discover(tmp_path)


def test_a_named_widgets_topics_and_actions_reach_the_page():
    page = web.page(web.discover(), ["keys", "all_keys"], WIDGETS["tabs"])
    assert "tabs" in page.topics and "ui/choose_tab" in page.actions


def test_a_page_without_a_named_widget_has_only_its_components_topics():
    page = web.page(web.discover(), ["tip", "keys"])
    assert "tabs" not in page.topics and "ui/choose_tab" not in page.actions


def test_a_named_widgets_files_load_after_its_components():
    page = web.page(web.discover(), ["keys", "all_keys"], WIDGETS["tabs"])
    scripts = [line for line in page.html.splitlines() if line.startswith("<script")]
    assert scripts[-1] == '<script src="../widgets/tabs/tabs.js"></script>'


def test_the_page_config_names_the_widget():
    script = web.widget_config(("keys", "all_keys"), "tabs", ("tabs",), None)
    assert '"components": ["keys", "all_keys"], "widget": "tabs"' in script


def test_only_titled_components_can_be_tabs_keys_first():
    names = [name for name, _ in web.tab_titles(web.discover())]
    assert names == ["keys", "all_keys", "trade_table"]
