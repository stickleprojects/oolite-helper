import json
from pathlib import Path

import pytest

from helper import plist
from helper.keys import Keymap, from_override
from helper.layout import widgets_from_specs, windows_from_specs
from helper.model import Model
from helper.plugins import TOPICS, WebWidgets, discover, read_manifest
from helper.widgets import COMPONENTS, WidgetSpec, WindowSpec, load_widgets, title_height

GAME = {"type": "window/game", "geometry": [100, 200, 1280, 720], "frame": [2, 2, 24, 2]}
LAMP = """\
name = "lamp"
version = "1.0.0"
api = 1
topics = ["drive", "context"]
width = 200
height = 60
"""


def make_plugin(folder, name="lamp", manifest=LAMP, page=True):
    root = folder / name
    root.mkdir(parents=True)
    (root / "plugin.toml").write_text(manifest)
    if page:
        (root / "index.html").write_text("<p>")
    return root


# -- manifests and discovery -------------------------------------------------


def test_a_good_manifest_is_read(tmp_path):
    manifest = read_manifest(make_plugin(tmp_path))
    assert (manifest.name, manifest.api, manifest.topics) == ("lamp", 1, ("drive", "context"))
    assert (manifest.width, manifest.height, manifest.entry) == (200, 60, "index.html")
    assert manifest.root == str(tmp_path / "lamp")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('name = "lamp"', 'name = "other"'), "name must match its folder"),
        (("api = 1", "api = 2"), "needs api 2; this helper has api 1"),
        (('"drive"', '"secrets"'), "topics must be a list of"),
        (("width = 200", "width = 5"), "width must be a whole number of pixels"),
        (("height = 60", 'height = "tall"'), "height must be a whole number"),
        (('version = "1.0.0"', "version = 1"), "version must be a string"),
        (("api = 1", 'api = 1\ncolour = "red"'), "unknown settings: colour"),
        (("api = 1", 'api = 1\nentry = "../index.html"'), "isn't in the plugin's folder"),
        (("api = 1", "api = = 1"), "can't read plugin.toml"),
    ],
)
def test_bad_manifests_say_whats_wrong(tmp_path, change, message):
    root = make_plugin(tmp_path, manifest=LAMP.replace(*change))
    with pytest.raises(ValueError, match=message):
        read_manifest(root)


def test_plugin_names_are_url_safe_and_not_built_in_components(tmp_path):
    for name, message in (("Lamp", "lower case"), ("drive", "the helper's components")):
        root = make_plugin(tmp_path, name, LAMP.replace('"lamp"', f'"{name}"'))
        with pytest.raises(ValueError, match=message):
            read_manifest(root)


def test_discover_finds_good_and_broken_plugins_and_skips_other_folders(tmp_path):
    make_plugin(tmp_path)
    make_plugin(tmp_path, "nopage", LAMP.replace('"lamp"', '"nopage"'), page=False)
    (tmp_path / "notes").mkdir()
    found, broken = discover(tmp_path)
    assert list(found) == ["lamp"]
    assert list(broken) == ["nopage"] and "entry page" in broken["nopage"]
    assert discover(tmp_path / "missing") == ({}, {})


def test_widgets_can_name_a_plugin_but_only_on_its_own(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[[widgets]]\ncomponents = ["lamp"]\ndock = "game:top"\n')
    (spec,) = load_widgets(path, plugins={"lamp"})
    assert spec.components == ("lamp",)
    with pytest.raises(SystemExit, match="components must be one or more of"):
        load_widgets(path)  # no such plugin
    path.write_text('[[widgets]]\ncomponents = ["lamp", "drive"]\n')
    with pytest.raises(SystemExit, match="must be the only component"):
        load_widgets(path, plugins={"lamp"})


# -- the topics plugins can read -------------------------------------------


def test_every_topic_is_json_in_every_state():
    model = Model()
    messages = (
        {"type": "ready", "docked": False, "alert": 1},
        {"type": "mass_lock", "by": "planet"},
        {"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747},
        {"type": "ready", "docked": True, "alert": 0},
    )
    for message in (None, *messages):
        if message:
            model.dispatch(message)
        for name, (select, *_) in TOPICS.items():
            assert json.loads(json.dumps(select(model))) == select(model), name


def test_topics_have_documented_shapes():
    model = Model()
    model.dispatch({"type": "ready", "docked": False, "alert": 3})
    model.dispatch({"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747})
    value = {name: select(model) for name, (select, *_) in TOPICS.items()}
    assert value["context"] == "red alert" and value["alert"] == "red"
    assert value["jump_blocker"] == {"by": "Coriolis Station", "clear_at": 6747}
    assert value["drive"] == {
        "torus": {"ok": True, "by": None},
        "jump": {"ok": False, "by": "Coriolis Station"},
    }


# -- widgets: windows, topics and problems -----------------------------------


class StubHost:
    def __init__(self):
        self.windows, self.published, self.events = {}, [], []
        self.frames = {}

    def sync(self, windows, frames=None):
        self.windows, self.frames = windows, frames or {}

    def publish(self, wid, topic, value):
        self.published.append((wid, topic, value))

    def poll(self):
        events, self.events = self.events, []
        return events

    def close(self):
        pass


@pytest.fixture
def widgets(tmp_path):
    make_plugin(tmp_path)
    make_plugin(tmp_path, "bad", LAMP.replace('"lamp"', '"bad"').replace("api = 1", "api = 9"))
    manifests, broken = discover(tmp_path)
    specs = [WidgetSpec(components=("lamp",), dock="game:top"), WidgetSpec(components=("gone",))]
    model = Model(layout=widgets_from_specs(specs))
    host = StubHost()
    made = WebWidgets(model, manifests, broken, host=host)
    return model, host, made


def test_panels_get_only_their_topics_and_their_changes(widgets):
    model, host, _ = widgets
    assert host.published == [
        ("widget1:lamp", "drive", None),
        ("widget1:lamp", "context", "waiting for game"),
    ]
    host.published.clear()
    model.dispatch({"type": "ready", "docked": True, "alert": 0})
    model.notify()
    assert host.published == [
        ("widget1:lamp", "drive", None),
        ("widget1:lamp", "context", "docked"),
    ]


def test_panels_dock_like_widgets_and_follow_page_resizes(widgets):
    model, host, made = widgets
    assert host.windows["widget1:lamp"].rect is None  # no game window yet
    model.dispatch({**GAME, "active": True})
    model.notify()
    window = host.windows["widget1:lamp"]
    assert (window.plugin, window.root) == ("lamp", made.widgets["widget1:lamp"].root)
    assert window.rect == (100, 200 - 24 - 60, 1280, 60)  # above the title bar, full width
    host.events = [
        {"ev": "page", "id": "widget1:lamp", "msg": {"type": "resize", "width": 300, "height": 90}}
    ]
    made.tick()
    model.notify()
    assert host.windows["widget1:lamp"].rect == (100, 200 - 24 - 90, 1280, 90)
    model.dispatch({**GAME, "active": False})
    model.notify()
    assert host.windows["widget1:lamp"].rect is None  # hidden while the game isn't active


def test_problems_show_in_the_status_line(widgets):
    model, host, made = widgets
    status = model.status["plugins"]
    assert "plugin bad: needs api 9" in status and "plugin gone: not installed" in status
    host.events = [{"ev": "crashed", "id": "widget1:lamp", "reason": "crashed"}]
    made.tick()
    assert "plugin lamp: its page crashed" in model.status["plugins"]
    host.events = [{"ev": "unavailable", "message": "plugins can't start: no DISPLAY"}]
    made.tick()
    assert "no DISPLAY" in model.status["plugins"]
    host.events = [{"ev": "ready"}, {"ev": "loaded", "id": "widget1:lamp"}]
    made.tick()
    assert "lamp" not in model.status["plugins"] and "DISPLAY" not in model.status["plugins"]


def test_page_logs_go_to_the_helpers_log(widgets, capsys):
    _, host, made = widgets
    host.events = [{"ev": "page", "id": "widget1:lamp", "msg": {"type": "log", "text": "hello"}}]
    made.tick()
    assert "plugin lamp: hello" in capsys.readouterr().err


def test_no_plugin_widgets_means_no_web_host():
    made = WebWidgets(Model(), {})
    assert made.host is None
    made.tick()
    made.close()


# -- key bindings ---------------------------------------------------------------


def keyed_model():
    data = plist.load(Path(__file__).parent / "fixtures" / "keyconfig2.plist")
    keymap = Keymap(data["default"], {"key_roll_left": "Roll left"})
    return Model(keymap=keymap)


def test_key_sections_are_what_the_keys_tab_shows():
    model = keyed_model()
    model.dispatch({"type": "ready", "docked": False, "alert": 1})
    sections = TOPICS["key_sections"][0](model)
    assert [s["title"] for s in sections] == [title for title, _ in model.topic("sections")]
    flight = next(s for s in sections if any(k["action"] == "key_roll_left" for k in s["keys"]))
    roll = next(k for k in flight["keys"] if k["action"] == "key_roll_left")
    assert roll == {
        "action": "key_roll_left",
        "bindings": [{"key": "arrowLeft", "shift": False, "ctrl": False, "alt": False}],
        "keys": "←",
        "description": "Roll left",
        "available": True,
    }
    assert all(k["keys"] for s in sections for k in s["keys"])  # unbound ones left out
    json.dumps(sections)


def test_descriptions_carry_our_notes_and_work_without_a_keymap():
    assert keyed_model().describe("key_docking_music").endswith("(while docking computer is on)")
    assert Model().describe("key_launch_ship") == "launch ship"
    assert Model().keys("key_launch_ship") == ""


def test_a_plugin_gets_the_keys_it_lists(tmp_path):
    make_plugin(tmp_path, manifest=LAMP + 'keys = ["key_jumpdrive", "key_not_in_this_game"]\n')
    manifests, _ = discover(tmp_path)
    assert manifests["lamp"].keys == ("key_jumpdrive", "key_not_in_this_game")
    model, host = keyed_model(), StubHost()
    model.layout = widgets_from_specs([WidgetSpec(components=("lamp",))])
    WebWidgets(model, manifests, host=host)
    keys = {topic: value for _, topic, value in host.published}["keys"]
    assert keys["key_jumpdrive"]["keys"] == model.keys("key_jumpdrive") != ""
    assert keys["key_not_in_this_game"] == {
        "action": "key_not_in_this_game",
        "bindings": [],
        "keys": "",
        "description": "not in this game",
    }


def test_keys_in_a_manifest_must_be_action_names(tmp_path):
    root = make_plugin(tmp_path, manifest=LAMP + 'keys = ["rm -rf"]\n')
    with pytest.raises(ValueError, match="keys must be a list of game actions"):
        read_manifest(root)


# -- constants beside display text (localisation-ready) -------------------------


def test_bindings_are_constants_in_the_games_key_names():
    keymap = Keymap(
        {
            "key_a": [{"key": "L"}],  # a capital letter means Shift
            "key_b": [{"key": "c", "shift": "YES", "mod1": 1}, {"key": "f1", "mod2": "true"}],
            "key_c": [from_override({"key": 34, "mod1": 1})],  # Ctrl+" changed in the game
        },
        {},
    )
    off = {"shift": False, "ctrl": False, "alt": False}
    assert keymap.bindings_of("key_a") == [{"key": "l", **off, "shift": True}]
    assert keymap.bindings_of("key_b") == [
        {"key": "c", "shift": True, "ctrl": True, "alt": False},
        {"key": "f1", **off, "alt": True},
    ]
    assert keymap.bindings_of("key_c") == [{"key": '"', **off, "ctrl": True}]
    assert keymap.bindings_of("key_unbound") == []


def test_details_have_a_kind_and_fields_beside_their_text():
    model = Model(clock=lambda: 100.0)
    model.state._clock = model.clock
    model.dispatch({"type": "ready", "docked": False, "alert": 1})
    model.dispatch({"type": "countdown", "kind": "galactic", "seconds": 9})
    model.dispatch({"type": "autopilot", "on": True})
    details = TOPICS["details"][0](model)
    assert details[0] == {
        "kind": "countdown",
        "galactic": True,
        "seconds": 9,
        "text": "Galactic jump in 9s",
    }
    assert details[-1] == {"kind": "docking_computer", "text": "Docking computer on"}
    assert [d["text"] for d in details] == model.state.details


@pytest.mark.parametrize(
    ("messages", "status"),
    [
        (
            [{"type": "aegis", "inside": True, "clearance": "DOCKING_CLEARANCE_STATUS_GRANTED"}],
            "granted",
        ),
        ([{"type": "aegis", "inside": True, "clearance": None}], "none"),
        ([{"type": "aegis", "inside": True, "requiresClearance": False}], "not_required"),
        (
            [
                {"type": "aegis", "inside": True},
                {
                    "type": "clearance",
                    "status": "DOCKING_CLEARANCE_STATUS_NONE",
                    "event": "refused",
                },
            ],
            "refused",
        ),
    ],
)
def test_clearance_has_a_status_constant_beside_its_text(messages, status):
    model = Model()
    model.dispatch({"type": "ready", "docked": False, "alert": 1})
    for message in messages:
        model.dispatch(message)
    clearance = TOPICS["clearance"][0](model)
    assert clearance["status"] == status and clearance["text"]


def test_closed_and_moved_panels_follow_the_layout(widgets):
    model, host, _ = widgets
    model.dispatch({**GAME, "active": True})
    model.dispatch({"type": "layout/move_widget", "id": "widget1:lamp", "x": 5, "y": -3})
    model.notify()
    assert host.windows["widget1:lamp"].rect == (105, 200 - 24 - 60 - 3, 1280, 60)
    model.dispatch({"type": "layout/close_widget", "id": "widget1:lamp"})
    model.notify()
    assert host.windows["widget1:lamp"].rect is None
    model.dispatch({"type": "layout/open_widget", "id": "widget1:lamp"})
    model.notify()
    assert host.windows["widget1:lamp"].rect is not None


# -- components: a page the helper generates for each widget --------------------


@pytest.fixture
def page_widgets():
    specs = [WidgetSpec(components=("clearance", "drive"), dock="game:top")]
    model = Model(layout=widgets_from_specs(specs))
    host, handed = StubHost(), []
    made = WebWidgets(model, {}, host=host, components=COMPONENTS, fallback=handed.append)
    model.dispatch({**GAME, "active": True})
    model.notify()
    return model, host, made, handed


def test_components_get_a_page_of_their_own_and_hide_until_it_draws(page_widgets):
    model, host, made, _ = page_widgets
    window = host.windows["widget1:clearance"]
    assert (window.plugin, window.rect) == ("helper", None)
    extras = dict(window.extras)
    assert extras["widget.js"] == (
        'globalThis.OOLITE_WIDGET = {"components": ["clearance", "drive"], "widget": null, '
        '"topics": ["clearance", "context", "drive"], "width": null, "height": null};\n'
    )
    host.events = [
        {"ev": "page", "id": "widget1:clearance", "msg": {"type": "show", "shown": True}}
    ]
    made.tick()
    model.notify()
    assert host.windows["widget1:clearance"].rect is not None


def test_components_fall_back_to_tk_if_the_host_never_starts(page_widgets):
    model, host, made, handed = page_widgets
    host.events = [{"ev": "unavailable", "message": "plugins can't start: no gi"}]
    made.tick()
    model.notify()
    assert handed == [["widget1:clearance"]]
    assert "widget1:clearance" not in host.windows
    host.events = [{"ev": "unavailable", "message": "again"}]
    made.tick()
    assert len(handed) == 1  # only once


def test_no_fallback_once_the_host_has_worked(page_widgets):
    _, host, made, handed = page_widgets
    host.events = [{"ev": "ready"}, {"ev": "host_exited", "code": 1}]
    made.tick()
    assert handed == []


def test_a_widget_page_loads_reads_and_sends_only_what_its_components_need(page_widgets):
    _, host, made, _ = page_widgets
    manifest = made.widgets["widget1:clearance"]
    assert (manifest.topics, manifest.actions) == (("clearance", "context", "drive"), ())
    page = dict(host.windows["widget1:clearance"].extras)["widget.html"]
    assert '<script src="../components/drive/drive.js">' in page
    assert "trade_here" not in page and "keys" not in page


def test_a_widget_page_names_its_widget():
    specs = [WidgetSpec(components=("keys", "all_keys"), dock="game:right", widget="tabs")]
    model = Model(layout=widgets_from_specs(specs))
    host = StubHost()
    WebWidgets(model, {}, host=host, components=COMPONENTS)
    model.dispatch({**GAME, "active": True})
    model.notify()
    script = dict(host.windows["widget1:keys"].extras)["widget.js"]
    assert '"components": ["keys", "all_keys"], "widget": "tabs"' in script


def test_hide_empty_hides_a_page_with_nothing_to_show():
    specs = [WidgetSpec(components=("drive",), dock="game:top", hide_empty=True)]
    model = Model(layout=widgets_from_specs(specs))
    host = StubHost()
    made = WebWidgets(model, {}, host=host, components=COMPONENTS)
    model.dispatch({**GAME, "active": True})
    made.handle({"ev": "page", "id": "widget1:drive", "msg": {"type": "show", "shown": False}})
    model.notify()
    assert host.windows["widget1:drive"].rect is None


def test_an_empty_page_stays_shown_by_default():
    specs = [WidgetSpec(components=("drive",), dock="game:top")]
    model = Model(layout=widgets_from_specs(specs))
    host = StubHost()
    made = WebWidgets(model, {}, host=host, components=COMPONENTS)
    model.dispatch({**GAME, "active": True})
    made.handle({"ev": "page", "id": "widget1:drive", "msg": {"type": "show", "shown": False}})
    model.notify()
    assert host.windows["widget1:drive"].rect is not None


TRADING = WindowSpec("trading", "Trading", "game:right", width=640)


def trading_window():
    """Trade here filling a widgetwindow on the game's right, the hold under it,
    both drawn. Returns (the stub host, the WebWidgets, the model)."""
    inside = {"dock": "game:right", "width": 640, "window": "trading"}
    specs = [
        WidgetSpec(components=("trade_here",), fill=True, **inside),
        WidgetSpec(components=("hold",), height=310, **inside),
    ]
    model = Model(layout=widgets_from_specs(specs), windows=windows_from_specs([TRADING]))
    host = StubHost()
    made = WebWidgets(model, {}, host=host, components=COMPONENTS)
    model.dispatch({**GAME, "active": True})
    for wid in ("widget1:trade_here", "widget2:hold"):
        made.handle({"ev": "page", "id": wid, "msg": {"type": "show", "shown": True}})
    model.notify()
    return host, made, model


def edge_dragged(made, rect, done):
    made.handle(
        {"ev": "frame", "id": "trading", "msg": {"type": "resize", "rect": rect, "done": done}}
    )


def test_a_widgetwindow_beside_the_game_is_the_game_windows_height():
    assert trading_window()[0].frames["trading"].rect == (
        100 + 1280 + 2,
        200 - 24,
        640,
        24 + 720 + 2,
    )


def test_a_widgetwindow_has_its_own_title():
    assert trading_window()[0].frames["trading"].title == "Trading"


def test_widgets_in_a_widgetwindow_go_into_its_frame():
    windows = trading_window()[0].windows
    assert [windows[wid].frame for wid in ("widget1:trade_here", "widget2:hold")] == ["trading"] * 2


def test_the_filling_widget_takes_what_the_others_leave_under_the_title():
    windows, title = trading_window()[0].windows, title_height(TRADING)
    top, height = 200 - 24, 24 + 720 + 2  # the game window, title bar and borders included
    assert windows["widget1:trade_here"].rect == (1382, top + title, 640, height - title - 310)
    assert windows["widget2:hold"].rect == (1382, top + height - 310, 640, 310)


def test_a_widgetwindows_pencil_puts_just_it_into_edit_mode():
    host, made, _ = trading_window()
    made.handle({"ev": "frame", "id": "trading", "msg": {"type": "edit"}})
    assert host.frames["trading"].editing


def test_beside_the_game_only_its_far_edge_resizes_it():
    assert trading_window()[0].frames["trading"].edges == ("right",)


def test_an_edge_dragged_outside_edit_mode_does_nothing():
    host, made, _ = trading_window()
    edge_dragged(made, [1382, 176, 700, 746], True)
    assert host.frames["trading"].rect[2] == 640


def test_while_an_edge_is_dragged_the_widgetwindow_follows_it():
    host, made, _ = trading_window()
    made.handle({"ev": "frame", "id": "trading", "msg": {"type": "edit"}})
    edge_dragged(made, [1382, 176, 700, 746], False)
    assert host.frames["trading"].rect == (1382, 176, 700, 746)


def test_on_release_the_new_width_goes_into_the_layout():
    host, made, model = trading_window()
    made.handle({"ev": "frame", "id": "trading", "msg": {"type": "edit"}})
    edge_dragged(made, [1382, 176, 700, 746], True)
    assert model.topic("windows")[0].spec.width == 700
