"""Plugins (#59): discovery, the topics they can read, and their windows.

A plugin is a folder in ~/.config/oolite-helper/plugins/<name>/ holding a
plugin.toml and its pages:

    name = "jump-lamp"           # must match the folder; lower case, digits, "-"
    version = "1.0.0"
    api = 1                      # the version of the `oolite` object it was written for
    topics = ["drive"]           # what it reads: names from TOPICS below
    keys = ["key_jumpdrive"]     # optional: these actions' keys, as the "keys" topic
    width = 200                  # its default size, until the page calls oolite.resize()
    height = 60
    entry = "index.html"         # optional
    description = "Torus and jump status as two lamps"   # optional

It's shown like a built-in view, in a widget of its own:

    [[widgets]]
    views = ["jump-lamp"]
    dock = "game:top"

Pages run sandboxed in the web host (helper/webhost). They get only the topics
they list, as plain JSON in the shapes documented in TOPICS: a public API,
kept stable for each `api` version, so the model's internals can change
without breaking plugins.

Constants for logic, text for showing: anything meant to be read by the
player ("text", "keys", "description") comes with constants beside it
("kind", "status", "action", "bindings"), so a plugin never has to parse
display text, and keeps working if the text is ever in another language
(Oolite has language add-ons; the helper's own words are English for now).
"""

import os
import re
import sys
import tomllib
from dataclasses import dataclass

from . import config
from .webhost import WebHost, WebWindow
from .widgets import VIEWS, place

API = 1
DIR = os.path.join(os.path.dirname(config.PATH), "plugins")
NAME = re.compile(r"[a-z][a-z0-9-]{0,39}")  # also the host in plugin://<name>/
ALERTS = {0: "docked", 1: "green", 2: "yellow", 3: "red"}


def _location(model):
    system, reached, aimed_at = model.topic("location")
    return {"system": system, "reached_target": reached, "aimed_at": aimed_at}


def _drive(model):
    lamps = {
        label.lower(): {"ok": ok, "by": by or None} for label, ok, by in model.topic("indicators")
    }
    return lamps or None


def _jump_blocker(model):
    blocker = model.topic("jump_blocker")
    return {"by": blocker["by"], "clear_at": blocker.get("clearAt")} if blocker else None


def _clearance(model):
    badge = model.topic("clearance")
    if badge is None:
        return None
    text, colour, flashes = badge
    state = model.state
    if state.requires_clearance is False:
        status = "not_required"
    elif state.clearance_refused:
        status = "refused"
    else:
        status = (state.clearance or "DOCKING_CLEARANCE_STATUS_NONE").removeprefix(
            "DOCKING_CLEARANCE_STATUS_"
        )
        status = status.lower()
    return {"status": status, "text": text, "colour": colour, "flashes": flashes}


def _details(model):
    return [
        {"kind": kind, **fields, "text": text} for kind, fields, text in model.state.detail_items
    ]


def key_info(model, action):
    """An action's keys: constants (action, bindings) and the Keys tab's text (keys, description).

    keys is "" and bindings [] if it's unbound.
    """
    return {
        "action": action,
        "bindings": model.bindings(action),
        "keys": model.keys(action),
        "description": model.describe(action),
    }


def _key_sections(model):
    return [
        {"title": title, "keys": [key_info(model, a) for a in actions if model.keys(a)]}
        for title, actions in model.topic("sections")
    ]


def _screen(model):
    gui, view = model.topic("screen")
    return {"gui": gui, "view": view}


# name -> (selector giving JSON, what it is). The shapes are the plugin API:
# add topics freely, but changing a shape needs a new API version.
TOPICS = {
    "context": (
        lambda m: m.topic("context"),
        'what the player is doing: "docked", "flying", "near station", "red alert", '
        '"jump countdown", "menu", "ship destroyed", "waiting for game" or "game not running"',
    ),
    "alert": (
        lambda m: ALERTS.get(m.state.alert),
        '"docked", "green", "yellow" or "red"; null before the game says',
    ),
    "location": (
        _location,
        '{"system": name or null, "reached_target": true if the last jump arrived where '
        'it was aimed, "aimed_at": the intended system when a jump went elsewhere, or null}',
    ),
    "screen": (_screen, '{"gui": the game screen, e.g. "GUI_SCREEN_STATUS", "view": the view}'),
    "details": (
        _details,
        'short notes: [{"kind": "countdown", "galactic": false, "seconds": 9, '
        '"text": "Jump in 9s"}, {"kind": "docking_computer", "text": "Docking computer on"}, '
        '{"kind": "jump_failed", '
        '"reason": ..., "text": ...}, {"kind": "destroyed", "by": ..., "cause": ..., "text": ...}]',
    ),
    "drive": (
        _drive,
        'while flying: {"torus": {"ok": bool, "by": ...}, "jump": {"ok": bool, "by": ...}}, '
        'else null; by is what blocks it (a ship\'s name, or "planet" or "sun"), or null',
    ),
    "mass_lock": (
        lambda m: m.topic("mass_lock"),
        'what locks the torus drive: a ship\'s name, or "planet" or "sun"; null if nothing',
    ),
    "jump_blocker": (
        _jump_blocker,
        '{"by": the ship or station in the way, "clear_at": metres away it stops blocking}, '
        "or null",
    ),
    "clearance": (
        _clearance,
        'near a station: {"status": "none", "requested", "granted", "timing_out", '
        '"not_required" or "refused", "text": "Cleared to dock", "colour": "green", '
        '"flashes": bool}, else null',
    ),
    "key_sections": (
        _key_sections,
        'what the Keys tab shows now: [{"title": "Flight", "keys": [{"action": "key_roll_left", '
        '"bindings": [{"key": "arrowLeft", "shift": false, "ctrl": false, "alt": false}], '
        '"keys": "←", "description": "Roll left"}, ...]}, ...]; unbound actions are left out',
    ),
}
# Not in TOPICS: "keys", the actions a plugin lists in its manifest, as
# {action: {"action", "keys", "description"}}. Key names and wording come from
# the game's files and the player's settings, like everywhere else.
KEYS_TOPIC = "keys"
ACTION = re.compile(r"key_[a-z0-9_]{1,60}")


@dataclass(frozen=True)
class Manifest:
    name: str
    root: str  # the plugin's folder
    version: str
    api: int
    topics: tuple
    width: int
    height: int
    entry: str = "index.html"
    description: str = ""
    keys: tuple = ()  # actions whose keys it wants (the "keys" topic)


def read_manifest(root):
    """The Manifest in root/plugin.toml; raises ValueError saying what's wrong."""
    folder = os.path.basename(os.path.normpath(root))
    try:
        with open(os.path.join(root, "plugin.toml"), "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"can't read plugin.toml: {exc}") from exc
    known = set(Manifest.__dataclass_fields__) - {"root"}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
    name = data.get("name")
    if name != folder:
        raise ValueError(f"name must match its folder, {folder!r}")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("name must be lower case letters, digits and -, up to 40")
    if name in VIEWS:
        raise ValueError(f"{name!r} is the name of a built-in view")
    if data.get("api") != API:
        raise ValueError(f"needs api {data.get('api')!r}; this helper has api {API}")
    if not isinstance(data.get("version"), str):
        raise ValueError('version must be a string, e.g. "1.0.0"')
    topics = data.get("topics", [])
    if not isinstance(topics, list) or not all(t in TOPICS for t in topics):
        raise ValueError(f"topics must be a list of: {', '.join(TOPICS)}")
    for size in ("width", "height"):
        value = data.get(size)
        if not isinstance(value, int) or isinstance(value, bool) or not 20 <= value <= 4000:
            raise ValueError(f"{size} must be a whole number of pixels, 20 to 4000")
    entry = data.get("entry", "index.html")
    full = os.path.realpath(os.path.join(root, str(entry)))
    if not full.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(full):
        raise ValueError(f"entry page {entry!r} isn't in the plugin's folder")
    keys = data.get("keys", [])
    if not isinstance(keys, list) or not all(
        isinstance(k, str) and ACTION.fullmatch(k) for k in keys
    ):
        raise ValueError('keys must be a list of game actions, e.g. ["key_jumpdrive"]')
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ValueError("description must be a string")
    return Manifest(
        **{**data, "root": os.path.abspath(root), "topics": tuple(topics), "keys": tuple(keys)}
    )


def discover(folder=DIR):
    """({name: Manifest}, {name: why it can't load}) for the plugin folders in folder."""
    found, broken = {}, {}
    if not os.path.isdir(folder):
        return found, broken
    for name in sorted(os.listdir(folder)):
        root = os.path.join(folder, name)
        if not os.path.isfile(os.path.join(root, "plugin.toml")):
            continue
        try:
            found[name] = read_manifest(root)
        except ValueError as exc:
            broken[name] = str(exc)
    return found, broken


class PluginPanels:
    """The widgets that show plugins: their windows, placement and topics.

    Call tick() from the helper's poll loop; it reads the web host's events
    and reports problems in the status line (status["plugins"]).
    """

    def __init__(self, model, specs, manifests, broken=(), monitors=(), host=None):
        broken = dict(broken)
        self.model = model
        self.monitors = monitors
        # panel id, "host" or "plugin:<name>" -> message for the status line
        self.problems = {f"plugin:{name}": f"plugin {name}: {why}" for name, why in broken.items()}
        self.panels = {}  # panel id -> (spec, manifest)
        self.sizes = {}  # panel id -> (w, h): the manifest's, or what the page asked for
        for n, spec in enumerate(specs, start=1):
            name = spec.views[0]
            wid = f"widget{n}:{name}"  # stable while the config doesn't change
            if name in manifests:
                manifest = manifests[name]
                self.panels[wid] = (spec, manifest)
                self.sizes[wid] = (manifest.width, manifest.height)
            elif name not in broken:  # broken ones are reported already
                self.problems[wid] = f"plugin {name}: not installed"
        self.host = host or (WebHost() if self.panels else None)
        self.subscriptions = [
            model.watch(lambda m, wid=wid: self.topics(wid), lambda v, wid=wid: self.send(wid, v))
            for wid in self.panels
        ]
        # Selectors run on every notify pass, so a page's resize (self.sizes)
        # is placed on the next one without telling the model.
        self.subscriptions.append(model.watch(self.windows, self.sync))
        self.report()

    def topics(self, wid):
        _, manifest = self.panels[wid]
        values = [(name, TOPICS[name][0](self.model)) for name in manifest.topics]
        if manifest.keys:
            keys = {action: key_info(self.model, action) for action in manifest.keys}
            values.append((KEYS_TOPIC, keys))
        return tuple(values)

    def send(self, wid, values):
        for name, value in values:
            self.host.publish(wid, name, value)

    def windows(self, model):
        game_window = model.topic("game_window")
        windows = {}
        for wid, (spec, manifest) in self.panels.items():
            rect = place(spec, game_window, self.sizes[wid], self.monitors)
            windows[wid] = WebWindow(manifest.name, manifest.root, manifest.entry, rect)
        return windows

    def sync(self, windows):
        if self.host is not None:
            self.host.sync(windows)

    def tick(self):
        if self.host is None:
            return
        changed = False
        for event in self.host.poll():
            changed |= self.handle(event)
        if changed:
            self.report()

    def handle(self, event):
        """Act on one web host event; True if the problems changed."""
        kind, wid = event.get("ev"), event.get("id")
        name = self.panels[wid][1].name if wid in self.panels else None
        if kind == "page" and name:
            msg = event["msg"]
            if msg["type"] == "resize":
                self.sizes[wid] = (msg["width"], msg["height"])  # placed on the next pass
            elif msg["type"] == "log":
                print(f"oolite-helper: plugin {name}: {msg['text']}", file=sys.stderr)
            return False
        if kind in ("error", "crashed") and name:
            why = event.get("message") or f"its page {event.get('reason', 'crashed')}"
            self.problems[wid] = f"plugin {name}: {why}"
        elif kind == "loaded" and wid in self.problems:
            del self.problems[wid]
        elif kind in ("unavailable", "host_exited"):
            self.problems["host"] = event.get("message") or "the plugin web host stopped"
        elif kind == "ready":
            self.problems.pop("host", None)
        else:
            return False
        return True

    def report(self):
        text = "; ".join(self.problems.values()) or None
        if text:
            print(f"oolite-helper: {text}", file=sys.stderr)
        self.model.set_status(plugins=text)

    def close(self):
        for subscription in self.subscriptions:
            subscription.cancel()
        if self.host is not None:
            self.host.close()
