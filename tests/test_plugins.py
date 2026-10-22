import json
from pathlib import Path

import pytest

from helper import plist
from helper.keys import Keymap
from helper.model import Model
from helper.plugins import TOPICS, PluginPanels, discover, read_manifest
from helper.widgets import WidgetSpec, load_widgets

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


def test_plugin_names_are_url_safe_and_not_built_in_views(tmp_path):
    for name, message in (("Lamp", "lower case"), ("drive", "built-in view")):
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
    path.write_text('[[widgets]]\nviews = ["lamp"]\ndock = "game:top"\n')
    (spec,) = load_widgets(path, plugins={"lamp"})
    assert spec.views == ("lamp",)
    with pytest.raises(SystemExit, match="views must be one or more of"):
        load_widgets(path)  # no such plugin
    path.write_text('[[widgets]]\nviews = ["lamp", "drive"]\n')
    with pytest.raises(SystemExit, match="must be the only view"):
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
        for name, (select, _) in TOPICS.items():
            assert json.loads(json.dumps(select(model))) == select(model), name


def test_topics_have_documented_shapes():
    model = Model()
    model.dispatch({"type": "ready", "docked": False, "alert": 3})
    model.dispatch({"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747})
    value = {name: select(model) for name, (select, _) in TOPICS.items()}
    assert value["context"] == "red alert" and value["alert"] == "red"
    assert value["jump_blocker"] == {"by": "Coriolis Station", "clear_at": 6747}
    assert value["drive"] == {
        "torus": {"ok": True, "why": ""},
        "jump": {"ok": False, "why": "Coriolis Station"},
    }


# -- panels: windows, topics and problems -----------------------------------


class StubHost:
    def __init__(self):
        self.windows, self.published, self.events = {}, [], []

    def sync(self, windows):
        self.windows = windows

    def publish(self, wid, topic, value):
        self.published.append((wid, topic, value))

    def poll(self):
        events, self.events = self.events, []
        return events

    def close(self):
        pass


@pytest.fixture
def panels(tmp_path):
    make_plugin(tmp_path)
    make_plugin(tmp_path, "bad", LAMP.replace('"lamp"', '"bad"').replace("api = 1", "api = 9"))
    manifests, broken = discover(tmp_path)
    model = Model()
    host = StubHost()
    specs = [WidgetSpec(views=("lamp",), dock="game:top"), WidgetSpec(views=("gone",))]
    made = PluginPanels(model, specs, manifests, broken, host=host)
    return model, host, made


def test_panels_get_only_their_topics_and_their_changes(panels):
    model, host, _ = panels
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


def test_panels_dock_like_widgets_and_follow_page_resizes(panels):
    model, host, made = panels
    assert host.windows["widget1:lamp"].rect is None  # no game window yet
    model.dispatch({**GAME, "active": True})
    model.notify()
    window = host.windows["widget1:lamp"]
    assert (window.plugin, window.root) == ("lamp", made.panels["widget1:lamp"][1].root)
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


def test_problems_show_in_the_status_line(panels):
    model, host, made = panels
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


def test_page_logs_go_to_the_helpers_log(panels, capsys):
    _, host, made = panels
    host.events = [{"ev": "page", "id": "widget1:lamp", "msg": {"type": "log", "text": "hello"}}]
    made.tick()
    assert "plugin lamp: hello" in capsys.readouterr().err


def test_no_plugin_widgets_means_no_web_host():
    made = PluginPanels(Model(), [], {})
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
        "keys": model.keys("key_roll_left"),
        "description": "Roll left",
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
    PluginPanels(model, [WidgetSpec(views=("lamp",))], manifests, host=host)
    keys = {topic: value for _, topic, value in host.published}["keys"]
    assert keys["key_jumpdrive"]["keys"] == model.keys("key_jumpdrive") != ""
    assert keys["key_not_in_this_game"] == {
        "action": "key_not_in_this_game",
        "keys": "",
        "description": "not in this game",
    }


def test_keys_in_a_manifest_must_be_action_names(tmp_path):
    root = make_plugin(tmp_path, manifest=LAMP + 'keys = ["rm -rf"]\n')
    with pytest.raises(ValueError, match="keys must be a list of game actions"):
        read_manifest(root)
