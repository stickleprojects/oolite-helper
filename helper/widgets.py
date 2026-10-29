"""Widgets: windows hosting one or more components, docked to the game or free (#50).

Terms: a component renders part of the model; a widget hosts one or more
components; a dock is a place beside the game window that holds widgets; the
layout (layout.py) places every widget, in a dock or free on a monitor.

Configured in config.toml as an array of [[widgets]] tables:

    [[widgets]]
    components = ["clearance", "drive"]  # built-in components (helper/web) or one plugin
    dock = "game:top"                # game:top / game:bottom / game:left / game:right

    [[widgets]]
    components = ["trade_here"]
    dock = "game:right"
    width = 520

    [[widgets]]                      # or free, on a monitor
    id = "drive-strip"               # optional stable id (layout.toml); see layout.py
    components = ["drive"]
    screen = "eDP-1"
    x = 0
    y = 0

    [[widgets]]                      # or a preset (#84), with any setting changed
    widget = "top-strip"             # helper/web/widgets/top-strip/widget.toml
    dock = "game:bottom"

A preset is a folder in helper/web/widgets/<name>/: a widget.toml with the
settings a [[widgets]] table takes, plus a description and named states, each
naming a state for each of its components:

    [states]
    "leaving the station" = {clearance = "away from stations", drive = "mass locked"}

and a generated README.md with a picture of it in each state (python -m
helper.harness --readmes). Its name is the widget's id unless the config gives
another.

A preset may also draw itself (#89): its own .js registers it with
Oolite.widget() (helper/web/lib/widget.js) and arranges its components, as the
tabs preset does. Then widget.toml may say what the widget itself reads and
sends, beyond its components' (topics, actions), and that every component
needs a title (titled = true: its tab label). Its own named states are in
<name>.states.json, over its own topics, and a [states] entry then names one
of them too, keyed by the preset's name.

Docked widgets sit outside the game window (above its title bar, below it, or
beside it), follow it when it moves, and show only while it's the active
window: the #50 spike found topmost widgets would otherwise cover other apps.
The helper only reads the game window's position; it never moves the game.

Widgets are web views by default: plugins.WebWidgets shows the built-in
components as a page built from helper/web. TkWidget below is the fallback,
for ui = "tk" or when the web host can't start; it shows the components that
have a Tk version (TK_COMPONENTS) and leaves the others out.
"""

import json
import os
import re
import tkinter as tk
import tomllib
from dataclasses import dataclass, replace

from . import config, web
from .layout import find
from .plugin_api import ACTIONS, TOPICS
from .tk.components.chips import ClearanceBadge, DriveChips
from .tk.components.style import BG, LAYOUTS, Style
from .tk.components.trade_here import TradeHere

COMPONENTS = web.discover()  # the built-in components: name -> web.WebComponent
# The ones with a Tk version, for the fallback: name -> factory(model, style,
# parent frame). Each packs itself into the frame.
TK_COMPONENTS = {
    "drive": DriveChips,  # TORUS ✓/✗ and JUMP ✓/✗
    "clearance": ClearanceBadge,  # docking clearance near a station
    "trade_here": TradeHere,  # hold, last market, best buys (while docked)
}
DOCKS = ("game:top", "game:bottom", "game:left", "game:right")
SHOW = ("with_game", "always")
WIDGET_ID = re.compile(r"[A-Za-z0-9_.:-]{1,60}")
WIDGETS_DIR = os.path.join(web.DIR, "widgets")  # the presets


@dataclass(frozen=True)
class WidgetSpec:
    components: tuple  # names
    dock: str | None = None  # one of DOCKS, or None for a free widget
    screen: str | None = None  # free widgets: monitor name; None = the whole desktop
    x: int = 0  # free: position on that monitor; docked: offset from the docked spot
    y: int = 0
    width: int | None = None  # None: the game's width (top/bottom) or what the components need
    height: int | None = None  # None: the game's height (left/right) or what the components need
    layout: str = "compact"  # from config.toml: compact when docked to the game, else large
    font_scale: float = 1.0
    show: str | None = None  # SHOW; default with_game when docked, always when free
    hide_empty: bool = True  # hide while its components have nothing to show
    id: str | None = None  # stable widget id (layout.toml); default "widget<n>:<first component>"
    widget: str | None = None  # the preset it came from, if any

    @property
    def shown(self):
        return self.show or ("with_game" if self.dock else "always")


def load_widgets(path=config.PATH, plugins=()):
    """The [[widgets]] from the config file; [] if none. Bad entries stop with a message.

    plugins: the names of the plugin folders found (#59). A plugin is a component
    from outside the helper, a web page in its own window, so it must be its
    widget's only component.
    """
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        entries = tomllib.load(f).get("widgets", [])
    if not isinstance(entries, list):
        raise SystemExit(f"{path}: widgets must be an array of [[widgets]] tables")
    return [_spec(path, n, entry, plugins) for n, entry in enumerate(entries, start=1)]


def _spec(path, n, entry, plugins=()):
    where = f"{path}: widget {n}"
    if not isinstance(entry, dict):
        raise SystemExit(f"{where} must be a table")
    if "widget" in entry:
        preset = PRESETS.get(entry["widget"])
        if preset is None:
            raise SystemExit(f"{where}: widget must be one of {', '.join(PRESETS)}")
        entry = {"id": preset.name, **preset.settings, **entry}
        if preset.titled:
            _check_titled(where, entry.get("components"))
    known = set(WidgetSpec.__dataclass_fields__)
    unknown = set(entry) - known
    if unknown:
        raise SystemExit(f"{where}: unknown settings: {', '.join(sorted(unknown))}")
    components = _components(where, entry.get("components"), plugins)
    checks = (
        ("dock", entry.get("dock") in (None, *DOCKS), f"one of {', '.join(DOCKS)}"),
        ("layout", entry.get("layout", "large") in LAYOUTS, f"one of {', '.join(LAYOUTS)}"),
        ("show", entry.get("show") in (None, *SHOW), f"one of {', '.join(SHOW)}"),
    )
    for name, ok, wanted in checks:
        if not ok:
            raise SystemExit(f"{where}: {name} must be {wanted}")
    wid = entry.get("id")
    if wid is not None and not (isinstance(wid, str) and WIDGET_ID.fullmatch(wid)):
        raise SystemExit(f"{where}: id must be letters, digits, '_', '.', ':' or '-'")
    for name in ("x", "y", "width", "height"):
        value = entry.get(name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise SystemExit(f"{where}: {name} must be a whole number of pixels")
    if not isinstance(entry.get("hide_empty", True), bool):
        raise SystemExit(f"{where}: hide_empty must be true or false")
    scale = entry.get("font_scale", 1.0)
    if not isinstance(scale, (int, float)) or isinstance(scale, bool) or scale <= 0:
        raise SystemExit(f"{where}: font_scale must be a positive number")
    # Strips docked to the game are compact unless asked; other widgets are large.
    layout = entry.get("layout", "compact" if entry.get("dock") else "large")
    return WidgetSpec(
        **{**entry, "components": components, "font_scale": float(scale), "layout": layout}
    )


def _components(where, components, plugins):
    """A widget's component names from config.toml. Stops with a message if they're wrong."""
    if isinstance(components, str):
        components = [components]
    if not isinstance(components, list) or not components:
        components = [None]  # reported below
    if len(components) == 1 and components[0] in plugins:
        return tuple(components)  # a plugin, alone
    if any(name in plugins for name in components):
        raise SystemExit(f"{where}: a plugin must be the only component in its widget")
    if not all(isinstance(name, str) and name in COMPONENTS for name in components):
        known = ", ".join((*COMPONENTS, *sorted(plugins)))
        raise SystemExit(f"{where}: components must be one or more of {known}")
    if len(set(components)) < len(components):
        raise SystemExit(f"{where}: each component can be in a widget only once")
    return tuple(components)


def _check_titled(where, components):
    """Stops with a message unless every component has a title (a tab label)."""
    if isinstance(components, str):
        components = [components]
    for name in components if isinstance(components, list) else ():
        if name in COMPONENTS and not COMPONENTS[name].title:
            titled = ", ".join(name for name, _ in web.tab_titles(COMPONENTS))
            raise SystemExit(f"{where}: {name} has no title, so it can't be here; try {titled}")


@dataclass(frozen=True)
class Preset:
    """A built-in widget (#84): helper/web/widgets/<name>/widget.toml."""

    name: str
    description: str
    settings: dict  # what a [[widgets]] table takes
    spec: WidgetSpec  # those settings, checked, with the name as its id
    states: tuple = ()  # ((name, {component: its state's name}), ...)
    topics: tuple = ()  # what the widget itself reads, beyond its components'
    actions: tuple = ()  # and may send
    titled: bool = False  # every component needs a title (its tab label)
    files: tuple = ()  # its own .css and .js files, relative to web.DIR
    own_states: tuple = ()  # ((name, {topic: value}), ...) from <name>.states.json


def read_preset(folder):
    """The Preset in folder/widget.toml; raises ValueError saying what's wrong."""
    name = os.path.basename(os.path.normpath(folder))
    path = os.path.join(folder, "widget.toml")
    with open(path, "rb") as f:
        settings = tomllib.load(f)
    description = settings.pop("description", "")
    states = settings.pop("states", {})
    topics, actions = settings.pop("topics", []), settings.pop("actions", [])
    titled = settings.pop("titled", False)
    if "id" in settings or "widget" in settings:
        raise ValueError(f"{path}: a preset's id is its folder name, and it can't use a preset")
    if not all(topic in TOPICS for topic in topics):
        raise ValueError(f"{path}: topics must be from plugin_api.TOPICS")
    if not all(action in ACTIONS for action in actions):
        raise ValueError(f"{path}: actions must be from plugin_api.ACTIONS")
    if not isinstance(titled, bool):
        raise ValueError(f"{path}: titled must be true or false")
    try:
        if titled:
            _check_titled(path, settings.get("components"))
        spec = replace(_spec(path, name, {**settings, "id": name}), widget=name)
    except SystemExit as error:
        raise ValueError(str(error)) from None
    own = _own_states(folder, name, topics)
    wanted = set(spec.components) | ({name} if own else set())
    for state, chosen in states.items():
        if not isinstance(chosen, dict) or set(chosen) != wanted:
            listed = ", ".join([*spec.components, *([name] if own else [])])
            raise ValueError(f"{path}: state {state!r} must name a state for each of {listed}")
        for part, choice in chosen.items():
            known = own if part == name else dict(COMPONENTS[part].states)
            if choice not in known:
                raise ValueError(f"{path}: state {state!r}: {part} has no state {choice!r}")
    files = sorted(
        f"widgets/{name}/{file}"
        for file in os.listdir(folder)
        if file.endswith((".css", ".js")) and not file.endswith(".test.js")
    )
    return Preset(
        name,
        description,
        settings,
        spec,
        tuple(states.items()),
        tuple(topics),
        tuple(actions),
        titled,
        tuple(files),
        tuple(own.items()),
    )


def _own_states(folder, name, topics):
    """A preset's own named states, {name: {topic: value}}, from <name>.states.json."""
    path = os.path.join(folder, f"{name}.states.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        named = json.load(f)
    for state, values in named.items():
        if not isinstance(values, dict) or not set(values) <= set(topics):
            raise ValueError(f"{path}: state {state!r} may only set the widget's own topics")
    return named


def discover_presets(folder=WIDGETS_DIR):
    """{name: Preset} for every built-in widget. A broken one is a bug: it raises."""
    if not os.path.isdir(folder):
        return {}
    return {
        name: read_preset(os.path.join(folder, name))
        for name in sorted(os.listdir(folder))
        if os.path.isfile(os.path.join(folder, name, "widget.toml"))
    }


PRESETS = discover_presets()


def place(spec, game_window, size, monitors=()):
    """(x, y, width, height) for a widget, or None when it should be hidden.

    game_window is the model's (geometry, frame, active); size is what the
    components ask for, (width, height).
    """
    geometry, frame, active = game_window
    if spec.shown == "with_game" and not (geometry and active):
        return None
    want_w, want_h = size
    if spec.dock is None:
        origin = next(((m.x, m.y) for m in monitors if m.name == spec.screen), (0, 0))
        return (origin[0] + spec.x, origin[1] + spec.y, spec.width or want_w, spec.height or want_h)
    if geometry is None:
        return None
    gx, gy, gw, gh = geometry
    left, right, top, bottom = frame
    side = spec.dock.split(":")[1]
    if side in ("top", "bottom"):
        w, h = spec.width or gw, spec.height or want_h
        y = gy - top - h if side == "top" else gy + gh + bottom
        return (gx + spec.x, y + spec.y, w, h)
    w, h = spec.width or want_w, spec.height or gh
    x = gx - left - w if side == "left" else gx + gw + right
    return (x + spec.x, gy + spec.y, w, h)


class TkWidget:
    """One widget as a Tk window (the fallback): its components, kept in place by
    watching the game window and the widget in the model's layout (moved,
    resized, closed)."""

    def __init__(self, root, model, wid, monitors=()):
        self.wid = wid
        spec = find(model.topic("layout"), wid).spec
        self.monitors = monitors
        self.window = tk.Toplevel(root, bg=BG)
        # Like the main window: not managed by the window manager, never takes
        # focus from the game (verified for widgets in the #50 spike), on top.
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.withdraw()
        width = spec.width or 600
        style = Style(width, spec.layout, spec.font_scale)
        frame = tk.Frame(self.window, bg=BG, padx=style.px(6), pady=style.px(4))
        frame.pack(fill="both", expand=True)
        self.components = [
            TK_COMPONENTS[name](model, style, frame)
            for name in spec.components
            if name in TK_COMPONENTS
        ]
        self.placed = None
        # Re-place when the game window moves or the components need a different size
        # (Trade here grows when you dock). Tk works sizes out when idle, so a
        # change made in one pass is seen on the next.
        # Components are drawn before this watcher runs (they subscribed first), so
        # their "empty" flags are current.
        self.subscription = model.watch(
            lambda m: (
                m.topic("game_window"),
                self.requested_size(),
                self.empty(),
                find(m.topic("layout"), wid),
            ),
            self.follow,
        )

    def empty(self):
        return all(component.empty for component in self.components)

    def requested_size(self):
        return (self.window.winfo_reqwidth(), self.window.winfo_reqheight())

    def follow(self, value):
        game_window, size, empty, widget = value
        hidden = widget is None or not widget.open or (empty and widget.spec.hide_empty)
        placed = None if hidden else place(widget.spec, game_window, size, self.monitors)
        if placed == self.placed:
            return
        self.placed = placed
        if placed is None:
            self.window.withdraw()
            return
        x, y, w, h = placed
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.deiconify()
        self.window.lift()

    def close(self):
        self.subscription.cancel()
        for component in self.components:
            component.close()
        self.window.destroy()
