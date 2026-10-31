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

It's a component from outside the helper, shown in a widget of its own:

    [[widgets]]
    components = ["jump-lamp"]
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

from . import config, web
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
from .widgets import COMPONENTS, WIDGETS, along, place, stack_offset

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
    if name in COMPONENTS or name == web.HOST:
        raise ValueError(f"{name!r} is the name of one of the helper's components")
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


def page_manifest(components, names, widget=None):
    """A Manifest for a widget of the helper's components: its generated page, and
    only those components' topics and actions (and its named widget's, widget)."""
    page = web.page(components, names, widget)
    return PageManifest(
        name=web.HOST,
        root=web.DIR,
        version="1",
        api=API,
        topics=page.topics,
        width=600,
        height=60,
        entry="_oolite/widget.html",
        actions=page.actions,
        page=page.html,
    )


@dataclass(frozen=True)
class PageManifest(Manifest):
    page: str = ""  # the generated widget.html


class WebWidgets:
    """The widgets that show plugins: their windows, placement and topics.

    Call tick() from the helper's poll loop; it reads the web host's events
    and reports problems in the status line (status["plugins"]).
    """

    def __init__(
        self, model, manifests, broken=(), monitors=(), host=None, components=None, fallback=None
    ):
        """components: the helper's components ({name: web.WebComponent}); each
        widget of them gets a page built from just its components. None leaves
        them to Tk. fallback(widget ids) is called once if the web host fails
        before it was ever ready, to show them with Tk."""
        broken = dict(broken)
        self.model = model
        self.monitors = monitors
        # widget id, "host" or "plugin:<name>" -> message for the status line
        self.problems = {f"plugin:{name}": f"plugin {name}: {why}" for name, why in broken.items()}
        self.manifests = manifests
        self.widgets = {}  # widget id -> manifest; placement comes from the layout topic
        self.sizes = {}  # widget id -> (w, h): the manifest's, or what the page asked for
        self.pages = {}  # widget id -> its components, for the pages the helper generates
        self.hidden = set()  # widget ids whose page said it has nothing to show
        self.undrawn = set()  # the helper's pages not drawn yet: hidden whatever hide_empty says
        self.fallback = fallback
        self.ever_ready = False
        for widget in model.topic("layout"):
            wid, name = widget.id, widget.spec.components[0]
            if name in COMPONENTS or name == web.HOST:
                if components is None:
                    continue  # a Tk widget
                named = WIDGETS.get(widget.spec.widget)
                manifest = page_manifest(components, widget.spec.components, named)
                self.widgets[wid] = manifest
                self.sizes[wid] = (manifest.width, manifest.height)
                self.pages[wid] = widget.spec.components
                self.undrawn.add(wid)
            elif name in manifests:
                manifest = manifests[name]
                self.widgets[wid] = manifest
                self.sizes[wid] = (manifest.width, manifest.height)
            elif name not in broken:  # broken ones are reported already
                self.problems[wid] = f"plugin {name}: not installed"
        self.host = host or (WebHost() if self.widgets else None)
        self.subscriptions = [
            model.watch(lambda m, wid=wid: self.topics(wid), lambda v, wid=wid: self.send(wid, v))
            for wid in self.widgets
        ]
        # Selectors run on every notify pass, so a page's resize (self.sizes)
        # is placed on the next one without telling the model.
        self.subscriptions.append(model.watch(self.windows, self.sync))
        self.report()

    def topics(self, wid):
        manifest = self.widgets.get(wid)
        if manifest is None:
            return ()  # handed to Tk (fall_back)
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
        widgets = model.topic("layout")
        layout = {widget.id: widget for widget in widgets}

        def shown(widget):
            wid, spec = widget.id, widget.spec
            empty = wid in self.undrawn or (wid in self.hidden and spec.hide_empty)
            return wid in self.widgets and widget.open and not empty

        def size_along(widget):  # for the widgets stacked in a dock (#80)
            return along(widget.spec, self.sizes[widget.id]) if shown(widget) else None

        windows = {}
        for wid, manifest in self.widgets.items():
            widget = layout[wid]
            spec = widget.spec
            offset = stack_offset(widgets, wid, size_along)
            rect = (
                place(spec, game_window, self.sizes[wid], self.monitors, offset)
                if shown(widget)
                else None
            )
            extras = (("theme.css", theme_css(spec.layout, spec.font_scale)), ("dev.js", DEV_JS))
            if wid in self.pages:
                script = web.widget_config(
                    spec.components, spec.widget, manifest.topics, spec.width, spec.height
                )
                extras += (("widget.html", manifest.page), ("widget.js", script))
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
        name = self.widgets[wid].name if wid in self.widgets else None
        if kind == "page" and name:
            msg = event["msg"]
            if msg["type"] == "resize":
                self.sizes[wid] = (msg["width"], msg["height"])  # placed on the next pass
            elif msg["type"] == "show":
                self.undrawn.discard(wid)
                (self.hidden.discard if msg["shown"] else self.hidden.add)(wid)
            elif msg["type"] == "log":
                print(f"oolite-helper: plugin {name}: {msg['text']}", file=sys.stderr)
            elif msg["type"] == "dispatch":
                self.dispatch(wid, msg["action"])
            return False
        if kind in ("error", "crashed") and name:
            why = event.get("message") or f"its page {event.get('reason', 'crashed')}"
            self.problems[wid] = f"plugin {name}: {why}"
        elif kind == "loaded" and wid in self.problems:
            del self.problems[wid]
        elif kind in ("unavailable", "host_exited"):
            self.problems["host"] = event.get("message") or "the plugin web host stopped"
            if not self.ever_ready and self.pages and self.fallback is not None:
                self.fall_back()
        elif kind == "ready":
            self.ever_ready = True
            self.problems.pop("host", None)
        else:
            return False
        return True

    def fall_back(self):
        """Hand the components to Tk: the web host never started."""
        ids = list(self.pages)
        for wid in ids:
            del self.widgets[wid], self.sizes[wid], self.pages[wid]
            self.hidden.discard(wid)
            self.undrawn.discard(wid)
        fallback, self.fallback = self.fallback, None
        fallback(ids)

    def dispatch(self, wid, action):
        """Apply a page's UI action if its manifest (a plugin's, or the one made
        for a page of the helper's components) allows it and it checks out."""
        manifest = self.widgets[wid]
        name = manifest.name
        checked = check_action(action, manifest.actions)
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
