"""Widgets: windows hosting one or more components, docked to the game or free (#50).

Terms: a component renders part of the model; a widget hosts one or more
components; a widgetwindow (#124) holds one or more widgets under its own title;
a dock is a place beside the game window; the layout (layout.py) places every
widget, in a dock or free on a monitor.

Configured in config.toml as an array of [[widgets]] tables:

    [[widgets]]
    components = ["clearance", "drive"]  # components (helper/web) or one plugin
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

    [[widgets]]                      # or a widget by name (#84), with any setting changed
    widget = "top-strip"             # helper/web/widgets/top-strip/widget.toml
    dock = "game:bottom"

    [[widgetwindows]]                # or in a widgetwindow (#124): a title bar over
    id = "trading"                   # its widgets, stacked top to bottom
    title = "Trading"
    dock = "game:right"              # game:left/right: the game's height at this width;
    width = 640                      # game:top/bottom: the game's width at a set height
    widgets = [{widget = "trade-beside", height = "*"}, {widget = "hold-beside", height = 310}]

The widget with height = "*" takes what the others leave; with none, the last does.

A named widget is a folder in helper/web/widgets/<name>/: a widget.toml with
the settings a [[widgets]] table takes, plus a description and named states,
each naming a state for each of its components:

    [states]
    "leaving the station" = {clearance = "away from stations", drive = "mass locked"}

and a generated README.md with a picture of it in each state (python -m
helper.harness --readmes). Its name is the widget's id unless the config gives
another.

A named widget may also draw itself (#89): its own .js registers it with
Oolite.widget() (helper/web/lib/widget.js) and arranges its components, as the
tabs widget does. Then widget.toml may say what the widget itself reads and
sends, beyond its components' (topics, actions), and that every component
needs a title (titled = true: its tab label). Its own named states are in
<name>.states.json, over its own topics, and a [states] entry then names one
of them too, keyed by the widget's name.

Docked widgets sit outside the game window (above its title bar, below it, or
beside it), follow it when it moves, and show only while it's the active
window: the #50 spike found topmost widgets would otherwise cover other apps.
The helper only reads the game window's position; it never moves the game.

Widgets are web views by default: plugins.WebWidgets shows the
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

COMPONENTS = web.discover()  # the components: name -> web.WebComponent
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
WIDGETS_DIR = os.path.join(web.DIR, "widgets")  # the named widgets


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
    hide_empty: bool = False  # true: hide while its components (or plugin) have nothing to show
    id: str | None = None  # stable widget id (layout.toml); default "widget<n>:<first component>"
    widget: str | None = None  # the named widget it came from, if any
    window: str | None = None  # the widgetwindow it's in (its id); not a setting
    fill: bool = False  # in a widgetwindow: takes the height the others leave (height = "*")

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
        data = tomllib.load(f)
    entries = data.get("widgets", [])
    if not isinstance(entries, list):
        raise SystemExit(f"{path}: widgets must be an array of [[widgets]] tables")
    specs = [_spec(path, n, entry, plugins) for n, entry in enumerate(entries, start=1)]
    if "docks" in data:
        raise SystemExit(
            f"{path}: [[docks]] is now [[widgetwindows]] (#124): see config.example.toml"
        )
    return specs + _widgetwindows(path, data, plugins)[1]


@dataclass(frozen=True)
class WindowSpec:
    """A widgetwindow (#124): a title bar over one or more widgets, stacked top to bottom."""

    id: str
    title: str
    dock: str  # one of DOCKS
    width: int | None = None  # game:left/right: its width; top/bottom: the game's
    height: int | None = None  # game:top/bottom: its height; left/right: the game's
    layout: str = "compact"  # the title bar's text size
    font_scale: float = 1.0
    show: str = "with_game"  # SHOW


def load_widgetwindows(path=config.PATH, plugins=()):
    """The [[widgetwindows]] from the config file, as WindowSpecs; () if none."""
    if not os.path.exists(path):
        return ()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return _widgetwindows(path, data, plugins)[0]


def _widgetwindows(path, data, plugins):
    """(WindowSpecs, the WidgetSpecs of their widgets) for the [[widgetwindows]]
    tables. Each widget takes its widgetwindow's width and placement."""
    tables = data.get("widgetwindows", [])
    if not isinstance(tables, list):
        raise SystemExit(f"{path}: widgetwindows must be an array of [[widgetwindows]] tables")
    windows, specs = [], []
    for w, table in enumerate(tables, start=1):
        where = f"{path}: widgetwindow {w}"
        if not isinstance(table, dict):
            raise SystemExit(f"{where} must be a table")
        unknown = set(table) - {*WindowSpec.__dataclass_fields__, "widgets"}
        if unknown:
            raise SystemExit(f"{where}: unknown settings: {', '.join(sorted(unknown))}")
        wid, title, side = table.get("id"), table.get("title"), table.get("dock")
        if not (isinstance(wid, str) and WIDGET_ID.fullmatch(wid)):
            raise SystemExit(f"{where}: id must be letters, digits, '_', '.', ':' or '-'")
        if any(window.id == wid for window in windows):
            raise SystemExit(f"{where}: two widgetwindows have the id {wid!r}")
        if not isinstance(title, str) or not title:
            raise SystemExit(f"{where}: title must be some text")
        if side not in DOCKS:
            raise SystemExit(f"{where}: dock must be one of {', '.join(DOCKS)}")
        across = "width" if side in ("game:left", "game:right") else "height"
        size = table.get(across)
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise SystemExit(f"{where}: {across} must be a whole number of pixels")
        if table.get("width" if across == "height" else "height") is not None:
            raise SystemExit(f"{where}: docked to {side}, its other size is the game's")
        if table.get("layout", "compact") not in LAYOUTS:
            raise SystemExit(f"{where}: layout must be one of {', '.join(LAYOUTS)}")
        if table.get("show", "with_game") not in SHOW:
            raise SystemExit(f"{where}: show must be one of {', '.join(SHOW)}")
        scale = table.get("font_scale", 1.0)
        if not isinstance(scale, (int, float)) or isinstance(scale, bool) or scale <= 0:
            raise SystemExit(f"{where}: font_scale must be a positive number")
        entries = table.get("widgets")
        if not isinstance(entries, list) or not entries:
            raise SystemExit(f"{where}: widgets must be a list of widget tables")
        window = WindowSpec(**{k: v for k, v in table.items() if k != "widgets"})
        windows.append(replace(window, font_scale=float(scale)))
        fills = 0
        for n, entry in enumerate(entries, start=1):
            at = f"{where}, widget {n}"
            if not isinstance(entry, dict):
                raise SystemExit(f"{at} must be a table")
            placed = sorted({"dock", "screen", "x", "y", "width"} & set(entry))
            if placed:
                fixed = ", ".join(placed)
                raise SystemExit(f"{at}: its widgetwindow places it, so it can't set {fixed}")
            fill = entry.get("height") == "*"
            fills += fill
            entry = {k: v for k, v in entry.items() if not (k == "height" and fill)}
            width = size if across == "width" else None
            spec = _spec(path, n, {**entry, "dock": side, "width": width}, plugins, where=at)
            specs.append(replace(spec, window=wid, fill=fill))
        if fills > 1:
            raise SystemExit(f'{where}: only one widget can have height = "*"')
    return tuple(windows), specs


def _spec(path, n, entry, plugins=(), where=None):
    where = where or f"{path}: widget {n}"
    if not isinstance(entry, dict):
        raise SystemExit(f"{where} must be a table")
    if "widget" in entry:
        named = WIDGETS.get(entry["widget"])
        if named is None:
            raise SystemExit(f"{where}: widget must be one of {', '.join(WIDGETS)}")
        entry = {"id": named.name, **named.settings, **entry}
        if named.titled:
            _check_titled(where, entry.get("components"))
    known = set(WidgetSpec.__dataclass_fields__) - {"window", "fill"}
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
    if not isinstance(entry.get("hide_empty", False), bool):
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
class NamedWidget:
    """A widget a config entry can name (#84): helper/web/widgets/<name>/widget.toml."""

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


def read_widget(folder):
    """The NamedWidget in folder/widget.toml; raises ValueError saying what's wrong."""
    name = os.path.basename(os.path.normpath(folder))
    path = os.path.join(folder, "widget.toml")
    with open(path, "rb") as f:
        settings = tomllib.load(f)
    description = settings.pop("description", "")
    states = settings.pop("states", {})
    topics, actions = settings.pop("topics", []), settings.pop("actions", [])
    titled = settings.pop("titled", False)
    if "id" in settings or "widget" in settings:
        raise ValueError(
            f"{path}: a named widget's id is its folder name, and it can't name another"
        )
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
    return NamedWidget(
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
    """A named widget's own named states, {name: {topic: value}}, from <name>.states.json."""
    path = os.path.join(folder, f"{name}.states.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        named = json.load(f)
    for state, values in named.items():
        if not isinstance(values, dict) or not set(values) <= set(topics):
            raise ValueError(f"{path}: state {state!r} may only set the widget's own topics")
    return named


def discover_widgets(folder=WIDGETS_DIR):
    """{name: NamedWidget} for every widget folder. A broken one is a bug: it raises."""
    if not os.path.isdir(folder):
        return {}
    return {
        name: read_widget(os.path.join(folder, name))
        for name in sorted(os.listdir(folder))
        if os.path.isfile(os.path.join(folder, name, "widget.toml"))
    }


WIDGETS = discover_widgets()


def title_height(window):
    """The px height of a widgetwindow's title bar, for its layout and font_scale."""
    return round(40 * LAYOUTS[window.layout][0] * window.font_scale)


def window_rect(window, game_window):
    """(x, y, width, height) of a widgetwindow docked to the game, or None to hide it.
    Beside the game it's the game window's whole height, its title bar and
    borders included; above or below, its whole width."""
    geometry, frame, active = game_window
    if geometry is None or (window.show == "with_game" and not active):
        return None
    gx, gy, gw, gh = geometry
    left, right, top, bottom = frame
    side = window.dock.split(":")[1]
    if side in ("left", "right"):
        x = gx - left - window.width if side == "left" else gx + gw + right
        return (x, gy - top, window.width, top + gh + bottom)
    y = gy - top - window.height if side == "top" else gy + gh + bottom
    return (gx - left, y, left + gw + right, window.height)


def stacked(rect, title, heights):
    """Where a widgetwindow's widgets go, top to bottom under its title bar.

    rect is the widgetwindow's; heights is [(id, height or None if hidden,
    fills)] in order. The widget that fills (else the last shown one) takes
    what the others leave. Returns {id: (x, y, width, height) or None}.
    """
    x, y, w, h = rect
    shown = [(wid, height, fills) for wid, height, fills in heights if height is not None]
    filler = next((wid for wid, _, fills in shown if fills), shown[-1][0] if shown else None)
    left = h - title - sum(height for wid, height, _ in shown if wid != filler)
    rects, top = {}, y + title
    for wid, height, _ in heights:
        if height is None:
            rects[wid] = None
            continue
        height = max(0, left) if wid == filler else height
        rects[wid] = (x, top, w, height)
        top += height
    return rects


def place(spec, game_window, size, monitors=()):
    """(x, y, width, height) for a widget, or None when it should be hidden.

    game_window is the model's (geometry, frame, active); size is what the
    components ask for, (width, height). Not for widgets in a widgetwindow
    (stacked() places those).
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


def place_in_window(widgets, window, wid, game_window, height, title=None):
    """A widget's rect in its widgetwindow, or None. height(widget) is a widget's
    height, or None when it isn't shown, so the ones after it move up. title:
    the title bar's height (default title_height(window))."""
    rect = window_rect(window, game_window)
    if rect is None:
        return None
    inside = [w for w in widgets if w.spec.window == window.id]
    heights = [(w.id, height(w), w.spec.fill) for w in inside]
    title = title_height(window) if title is None else title
    return stacked(rect, title, heights)[wid]


def _configured_height(widget):
    """The Tk fallback has no title bars and stacks by the heights set in
    config.toml: an open widget's (0 if none), or None if it's closed."""
    return (widget.spec.height or 0) if widget.open else None


class TkWidget:
    """One widget as a Tk window (the fallback): its components, kept in place by
    watching the game window and the widget in the model's layout (moved,
    resized, closed). windows: {id: WindowSpec}, for one in a widgetwindow."""

    def __init__(self, root, model, wid, monitors=(), windows=None):
        self.wid = wid
        spec = find(model.topic("layout"), wid).spec
        self.monitors = monitors
        self.frame = (windows or {}).get(spec.window)
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
                self.in_window(m),
            ),
            self.follow,
        )

    def empty(self):
        return all(component.empty for component in self.components)

    def requested_size(self):
        return (self.window.winfo_reqwidth(), self.window.winfo_reqheight())

    def in_window(self, model):
        """Its rect in its widgetwindow (no title bar in Tk), or None."""
        if self.frame is None:
            return None
        layout, game_window = model.topic("layout"), model.topic("game_window")
        return place_in_window(layout, self.frame, self.wid, game_window, _configured_height, 0)

    def follow(self, value):
        game_window, size, empty, widget, in_window = value
        hidden = widget is None or not widget.open or (empty and widget.spec.hide_empty)
        if hidden:
            placed = None
        elif self.frame is not None:
            placed = in_window
        else:
            placed = place(widget.spec, game_window, size, self.monitors)
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
