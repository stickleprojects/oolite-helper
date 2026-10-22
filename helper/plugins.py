"""Plugins (#59): discovery, the topics they can read, and their windows.

A plugin is a folder in ~/.config/oolite-helper/plugins/<name>/ holding a
plugin.toml and its pages:

    name = "jump-lamp"           # must match the folder; lower case, digits, "-"
    version = "1.0.0"
    api = 1                      # the version of the `oolite` object it was written for
    topics = ["drive"]           # what it reads: names from plugin_api.TOPICS
    keys = ["key_jumpdrive"]     # optional: these actions' keys, as the "keys" topic
    actions = ["ui/choose_tab"]  # optional: what it may send with oolite.dispatch()
    width = 200                  # its default size, until the page calls oolite.resize()
    height = 60
    entry = "index.html"         # optional
    description = "Torus and jump status as two lamps"   # optional

It's shown like a built-in view, in a widget of its own:

    [[widgets]]
    views = ["jump-lamp"]
    dock = "game:top"

Pages run sandboxed in the web host (helper/webhost). They get only the topics
they list, and may send only the actions they list; both are the public
plugin API in helper/plugin_api.py. The helper's stylesheet is served to each
page as _oolite/theme.css.
"""

import os
import re
import sys
import tomllib
from dataclasses import dataclass

from . import config
from .plugin_api import (
    ACTIONS,
    API,
    DEV_JS,
    KEY_ACTION,
    KEYS_TOPIC,
    TOPICS,
    check_action,
    key_info,
    theme_css,
    topic_value,
)
from .webhost import WebHost, WebWindow
from .widgets import VIEWS, place

DIR = os.path.join(os.path.dirname(config.PATH), "plugins")
NAME = re.compile(r"[a-z][a-z0-9-]{0,39}")  # also the host in plugin://<name>/


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
    actions: tuple = ()  # UI actions it may dispatch (plugin_api.ACTIONS)


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
        isinstance(k, str) and KEY_ACTION.fullmatch(k) for k in keys
    ):
        raise ValueError('keys must be a list of game actions, e.g. ["key_jumpdrive"]')
    actions = data.get("actions", [])
    if not isinstance(actions, list) or not all(a in ACTIONS for a in actions):
        raise ValueError(f"actions must be a list of: {', '.join(ACTIONS)}")
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ValueError("description must be a string")
    return Manifest(
        **{
            **data,
            "root": os.path.abspath(root),
            "topics": tuple(topics),
            "keys": tuple(keys),
            "actions": tuple(actions),
        }
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
        self.manifests = manifests
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
        values = [(name, topic_value(self.model, name)) for name in manifest.topics]
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
            extras = (("theme.css", theme_css(spec.layout, spec.font_scale)), ("dev.js", DEV_JS))
            windows[wid] = WebWindow(manifest.name, manifest.root, manifest.entry, rect, extras)
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
            elif msg["type"] == "dispatch":
                self.dispatch(name, msg["action"])
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

    def dispatch(self, name, action):
        """Apply a plugin's UI action if its manifest allows it and it checks out."""
        checked = check_action(action, self.manifests[name].actions)
        if checked is None:
            print(f"oolite-helper: plugin {name}: refused action {action!r}", file=sys.stderr)
            return
        self.model.dispatch(checked)
        self.model.notify()

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
