import pytest

from helper import web
from helper.plugin_api import ACTIONS, TOPICS


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
