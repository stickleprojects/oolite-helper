import json
from pathlib import Path

import pytest

from helper import plist
from helper.keys import Keymap
from helper.layout import widgets_from_specs
from helper.markets import MarketStore
from helper.model import Model
from helper.plugin_api import TOPICS, check_action, theme_css, title_colours, topic_value
from helper.plugins import WebWidgets, discover
from helper.widgets import WidgetSpec
from tests.fakegame import load_scenario

ROOT = Path(__file__).parent.parent
ALL_UI = ["ui/choose_tab", "ui/open_commodity", "ui/choose_destination", "ui/change_quantity"]


def trading(tmp_path):
    """A model after the fake game's trade scenario: docked at Lave, Zaonce in range."""
    data = plist.load(ROOT / "tests" / "fixtures" / "keyconfig2.plist")
    model = Model(
        markets=MarketStore(tmp_path / "markets.json"), keymap=Keymap(data["default"], {})
    )
    model.dispatch({"type": "ready", "docked": True, "alert": 0})
    for step in load_scenario(ROOT / "scenarios" / "trade.yaml"):
        model.dispatch(step["msg"])
    return model


def values(model):
    return {name: topic_value(model, name) for name in TOPICS}


def test_every_topic_is_plain_json_through_a_trading_session(tmp_path):
    model = trading(tmp_path)
    states = [values(Model()), values(model)]
    model.dispatch({"type": "ui/choose_tab", "tab": "trade_table"})
    model.dispatch({"type": "ui/open_commodity", "commodity": "food"})
    states.append(values(model))
    model.dispatch({"type": "ui/choose_destination", "system": 8})
    model.dispatch({"type": "ui/change_quantity", "quantity": 2})
    states.append(values(model))
    for state in states:
        for name, value in state.items():
            assert json.loads(json.dumps(value)) == value, name


def test_trade_topics_give_constants_beside_their_text(tmp_path):
    model = trading(tmp_path)
    food = next(r for r in topic_value(model, "trade_rows") if r["commodity"] == "food")
    assert food["name"] == "Food" and food["unit"] == "t"
    assert food["here"] == {"price": 42, "note": "", "live": True}
    assert food["best"]["price"] == 48 and food["where"] == {"name": "Zaonce", "distance": 6.5}
    assert food["margin"] == 6

    model.dispatch({"type": "ui/open_commodity", "commodity": "food"})
    detail = topic_value(model, "trade_detail")
    assert detail["commodity"] == "food" and detail["row"] == food
    (zaonce,) = detail["offers"]
    # The scenario's economy 8 is outside the game's 0-7: no name rather than a guess.
    assert (zaonce["system_id"], zaonce["economy"], zaonce["economy_name"]) == (8, 8, None)
    assert detail["chosen"] == 8
    assert detail["limit"]["reason"] in ("on_sale", "credits", "cargo_space", "not_sold_here")
    assert detail["steps"] and all(isinstance(step, str) for step in detail["steps"])
    assert topic_value(model, "selection") == {
        "commodity": "food",
        "destination": None,
        "quantity": None,
    }


def test_tabs_show_keys_in_an_emergency_but_remember_the_choice():
    model = Model()
    model.dispatch({"type": "ready", "docked": False, "alert": 1})
    model.dispatch({"type": "ui/choose_tab", "tab": "trade_table"})
    tabs = topic_value(model, "tabs")
    assert (tabs["shown"], tabs["chosen"], tabs["urgent"]) == ("trade_table", "trade_table", False)
    assert [t["id"] for t in tabs["tabs"]] == ["keys", "all_keys", "trade_table"]
    model.dispatch({"type": "alert", "level": 3})
    tabs = topic_value(model, "tabs")
    assert (tabs["shown"], tabs["chosen"], tabs["urgent"]) == ("keys", "trade_table", True)


def test_the_status_line_has_a_kind():
    model = Model()
    assert topic_value(model, "status") == {"kind": None, "text": ""}
    model.set_status(last_message='{"type": "ready"}', plugins="plugin lamp: crashed")
    assert topic_value(model, "status") == {"kind": "warning", "text": "plugin lamp: crashed"}
    model.set_status(error="OSError: gone")
    assert topic_value(model, "status")["kind"] == "error"


def test_all_keys_lists_every_group_with_unbound_keys_too(tmp_path):
    groups = topic_value(trading(tmp_path), "all_keys")
    assert groups[0]["group"] == "header-screen-access"
    assert all(group["keys"] for group in groups)
    assert any(not key["keys"] and key["bindings"] == [] for g in groups for key in g["keys"])


def test_plugin_topics_are_computed_once_per_change(monkeypatch):
    calls = []
    select, every, doc = TOPICS["context"]
    monkeypatch.setitem(TOPICS, "context", (lambda m: calls.append(1) or select(m), every, doc))
    model = Model()
    topic_value(model, "context")
    topic_value(model, "context")
    assert len(calls) == 1
    model.dispatch({"type": "ready", "docked": True})
    topic_value(model, "context")
    assert len(calls) == 2


# -- actions -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "allowed", "expected"),
    [
        (
            {"type": "ui/choose_tab", "tab": "trade_table"},
            ALL_UI,
            {"type": "ui/choose_tab", "tab": "trade_table"},
        ),
        ({"type": "ui/open_commodity"}, ALL_UI, {"type": "ui/open_commodity", "commodity": None}),
        (
            {"type": "ui/change_quantity", "quantity": 5},
            ALL_UI,
            {"type": "ui/change_quantity", "quantity": 5},
        ),
        ({"type": "ui/choose_tab", "tab": "trade_table"}, [], None),  # not in its manifest
        ({"type": "ui/choose_tab", "tab": "secrets"}, ALL_UI, None),
        ({"type": "ui/choose_tab"}, ALL_UI, None),
        ({"type": "ui/open_commodity", "commodity": "../x"}, ALL_UI, None),
        ({"type": "ui/change_quantity", "quantity": True}, ALL_UI, None),
        ({"type": "ui/change_quantity", "quantity": -1}, ALL_UI, None),
        ({"type": "ui/choose_destination", "system": 256}, ALL_UI, None),
        ({"type": "ui/choose_tab", "tab": "keys", "extra": 1}, ALL_UI, None),
        ({"type": "jump", "to": "Lave"}, ALL_UI + ["jump"], None),  # not a plugin action at all
    ],
)
def test_actions_are_checked_against_the_manifest_and_their_fields(action, allowed, expected):
    assert check_action(action, allowed) == expected


@pytest.fixture
def clicky(tmp_path):
    root = tmp_path / "clicky"
    root.mkdir()
    (root / "index.html").write_text("<p>")
    (root / "plugin.toml").write_text(
        'name = "clicky"\nversion = "1"\napi = 1\nwidth = 100\nheight = 100\n'
        'topics = ["tabs"]\nactions = ["ui/choose_tab"]\n'
    )
    manifests, broken = discover(tmp_path)
    assert not broken
    model = Model(layout=widgets_from_specs([WidgetSpec(components=("clicky",), layout="large")]))
    widgets = WebWidgets(model, manifests, host=Stub())
    return model, widgets


class Stub:
    def __init__(self):
        self.windows, self.events = {}, []

    def sync(self, windows):
        self.windows = windows

    def publish(self, *args):
        pass

    def poll(self):
        events, self.events = self.events, []
        return events


def test_a_plugins_allowed_click_changes_the_shared_ui(clicky):
    model, widgets = clicky
    widgets.host.events = [
        {
            "ev": "page",
            "id": "widget1:clicky",
            "msg": {"type": "dispatch", "action": {"type": "ui/choose_tab", "tab": "all_keys"}},
        }
    ]
    widgets.tick()
    assert model.ui.tab == "all_keys"


def test_a_plugins_other_actions_are_refused(clicky, capsys):
    model, widgets = clicky
    action = {"type": "ui/open_commodity", "commodity": "food"}  # not in its manifest
    widgets.host.events = [
        {"ev": "page", "id": "widget1:clicky", "msg": {"type": "dispatch", "action": action}}
    ]
    widgets.tick()
    assert model.ui.commodity is None
    assert "refused action" in capsys.readouterr().err


def test_bad_actions_in_a_manifest_are_refused(tmp_path):
    root = tmp_path / "bad"
    root.mkdir()
    (root / "index.html").write_text("<p>")
    (root / "plugin.toml").write_text(
        'name = "bad"\nversion = "1"\napi = 1\nwidth = 100\nheight = 100\nactions = ["jump"]\n'
    )
    assert "actions must be a list of" in discover(tmp_path)[1]["bad"]


# -- the stylesheet ------------------------------------------------------------------


def test_each_plugin_gets_the_theme_for_its_widgets_layout(clicky):
    _, widgets = clicky
    window = widgets.host.windows["widget1:clicky"]
    extras = dict(window.extras)
    assert "--oo-accent: #ffb000;" in extras["theme.css"]
    assert "--oo-scale: 1;" in extras["theme.css"]  # layout = "large"
    assert "dev.js" in extras
    assert "--oo-scale: 0.6;" in theme_css("compact")
    assert "--oo-scale: 1.2;" in theme_css("compact", 2.0)


def test_the_theme_draws_a_window_edge_round_every_widget():
    assert "--oo-edge: #3c4650;" in theme_css()
    assert "border: 1px solid var(--oo-edge);" in theme_css()


def test_the_plugin_docs_cover_every_topic_and_action():
    docs = (ROOT / "docs" / "plugins.md").read_text()
    from helper.plugin_api import ACTIONS

    for name in (*TOPICS, *ACTIONS):
        assert f"`{name}`" in docs, name


def test_equipment_gives_ok_instead_of_the_games_status_string():
    model = Model()
    assert topic_value(model, "equipment") == {
        "items": [],
        "missiles": {"pylons": None, "loaded": []},
    }
    ecm = {"key": "EQ_ECM", "name": "E.C.M. System", "description": "ECM.", "count": 1}
    shield = {"key": "EQ_HEAT_SHIELD", "name": "Heat Shield", "description": "Hot.", "count": 2}
    missile = {"key": "EQ_MISSILE", "name": "Missile", "count": 3}
    model.dispatch(
        {
            "type": "equipment",
            "items": [
                {**ecm, "status": "EQUIPMENT_DAMAGED"},
                {**shield, "status": "EQUIPMENT_OK"},
            ],
            "missiles": {"capacity": 4, "loaded": [missile]},
        }
    )
    assert topic_value(model, "equipment") == {
        "items": [{**ecm, "ok": False}, {**shield, "ok": True}],
        "missiles": {"pylons": 4, "loaded": [missile]},
    }


def test_title_bars_take_the_desktops_colours(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: ("#0055aa", "#ffffff"))
    assert "--oo-title: #0055aa;\n  --oo-title-fg: #ffffff;" in theme_css()


def test_title_bars_fall_back_to_the_edge_colour(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: None)
    assert "--oo-title: #3c4650;\n  --oo-title-fg: #e6e6e6;" in theme_css()


def test_set_title_bar_colours_replace_the_desktops(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: ("#0055aa", "#ffffff"))
    theme = {"title_background": "#CC0000", "title_text": "#FFFFFF"}
    assert title_colours(theme) == ("#cc0000", "#ffffff")


def test_system_text_stays_readable_on_a_set_background(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: ("#0055aa", "#ffffff"))
    assert title_colours({"title_background": "#eeeeee", "title_text": "system"})[1] == "#000000"
