"""The player's settings (#135): config.toml, with layout.toml's changes on top,
as one pydantic model that checks everything when it's read and whenever the
helper changes it.

    settings, warnings = load(paths.CONFIG, plugins)  # stops with every problem
    settings.window, settings.theme, settings.widgets, settings.widgetwindows

config.toml has these tables, and nothing else:

    [window]            the laptop window (WindowSettings)
    [theme]             colours (Theme)
    [[widgets]]         widgets on their own (WidgetSpec)
    [[widgetwindows]]   widgetwindows and the widgets in them (WindowSpec, #124)

A named widget, helper/web/widgets/<name>/widget.toml, is read here too
(NamedWidget): its settings are a [[widgets]] table's.

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
A widgetwindow can also dock to a monitor's edge (dock = "screen:eDP-1:right",
its width in px or "%") or float on one (no dock; screen, x, y, width, height).

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

The rules live in the models: sizes are pixels or "N%"; height = "*" makes a
widget fill its widgetwindow (WidgetSpec.fill); "system" title colours are the
desktop's (Theme.colours); widgets and widgetwindows are compact unless told
otherwise; ids are unique. A widget accepts the core settings plus those its
components and named widget declare ([settings] name = "type", see
plugin_api.SETTING_TYPES); any other setting is a mistake. A widget naming a
component, plugin or named widget that isn't installed is left out with a
warning, not a mistake (Kieron, #135).

layout.toml holds the helper's own changes (moves, sizes, closes): load_layout
puts them on top through the same models, and ignores the whole file if any of
it is wrong, with a warning for each problem. `oolite-helper --check-config`
lists every problem in both files.
"""

import json
import math
import os
import re
import tomllib
from dataclasses import dataclass
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from . import paths, platform, web
from .colours import readable
from .layout import NONE, SAVED, Widget, widgets_from_specs, windows_from_specs
from .plugin_api import ACTIONS, SETTING_TYPES, TOPICS, declared_settings, setting_fits
from .tk.components.style import EDGE, FG, LAYOUTS

COMPONENTS = web.discover()  # the helper's components: name -> web.WebComponent
WIDGETS_DIR = os.path.join(web.DIR, "widgets")  # the named widgets
DOCKS = ("game:top", "game:bottom", "game:left", "game:right")
SIDES = ("top", "bottom", "left", "right")
SHOW = ("with_game", "always")
ANCHORS = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)
WIDGET_ID = re.compile(r"[A-Za-z0-9_.:-]{1,60}")
SCREEN_DOCK = re.compile(r"screen:(?P<monitor>[^:]+):(?P<edge>top|bottom|left|right)")
PERCENT = re.compile(r"\d+(\.\d+)?%")
COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")
GEOMETRY = re.compile(r"[1-9]\d*x[1-9]\d*[+-]\d+[+-]\d+")


class SettingsError(Exception):
    """config.toml is wrong: problems is a list of messages, one per mistake, and
    warnings what was found besides (widgets left out)."""

    def __init__(self, problems, warnings=()):
        super().__init__("\n".join(problems))
        self.problems = list(problems)
        self.warnings = list(warnings)


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _positive(value):
    return (_whole(value) or isinstance(value, float)) and math.isfinite(value) and value > 0


def _size(value):
    """Pixels, or "N%" of a monitor."""
    return (_whole(value) and value > 0) or (
        isinstance(value, str) and PERCENT.fullmatch(value) is not None
    )


def _pixels(name, value):
    if value is not None and not (_whole(value) and value > 0):
        raise ValueError(f"{name} must be a whole number of pixels")
    return value


def _choice(name, value, choices):
    if value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(map(str, choices))}")
    return value


class _Model(BaseModel):
    """Read-only, and any setting it doesn't know is a mistake."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    def changed(self, **values):
        """A copy with values changed, checked like config.toml (raises ValidationError)."""
        return type(self).model_validate({**self.model_dump(), **values})


def changed(model, **values):
    """model with values changed, checked: the helper's way to edit a setting."""
    return model.changed(**values)


# -- [window] ---------------------------------------------------------------


class WindowSettings(_Model):
    """[window]: where the laptop window goes and how its text looks."""

    screen: str | None = None  # xrandr name; default: first non-primary monitor
    width: int | str = "100%"  # pixels or % of that screen
    height: int | str = "100%"
    anchor: str = "top-left"
    margin: int = 0
    layout: str = "large"
    font_scale: float = 1.0
    geometry: str | None = None  # exact X geometry; overrides the above
    missing_equipment: str = "grey"  # or "hide"
    ui: str = "web"  # or "tk"

    @field_validator("width", "height", mode="before")
    @classmethod
    def _length(cls, value, info):
        text = str(value).strip() if not isinstance(value, bool) else ""
        if not (PERCENT.fullmatch(text) or text.isdigit()):
            raise ValueError(f'{info.field_name} must be pixels or a percentage like "40%"')
        return value

    @field_validator("anchor")
    @classmethod
    def _anchor(cls, value):
        return _choice("anchor", value, ANCHORS)

    @field_validator("margin", mode="before")
    @classmethod
    def _margin(cls, value):
        if not _whole(value) or value < 0:
            raise ValueError("margin must be a whole number of pixels")
        return value

    @field_validator("layout")
    @classmethod
    def _layout(cls, value):
        return _choice("layout", value, tuple(LAYOUTS))

    @field_validator("font_scale", mode="before")
    @classmethod
    def _font_scale(cls, value):
        if not _positive(value):
            raise ValueError("font_scale must be a positive number")
        return value

    @field_validator("geometry")
    @classmethod
    def _geometry(cls, value):
        if value is not None and not GEOMETRY.fullmatch(value):
            raise ValueError("geometry must match WxH+X+Y")
        return value

    @field_validator("missing_equipment")
    @classmethod
    def _missing(cls, value):
        return _choice("missing_equipment", value, ("grey", "hide"))

    @field_validator("ui")
    @classmethod
    def _ui(cls, value):
        return _choice("ui", value, ("web", "tk"))


# -- [theme] ----------------------------------------------------------------


class Theme(_Model):
    """[theme]: widgets' title bar colours, each "system" (the desktop's) or #rrggbb."""

    title_background: str = "system"
    title_text: str = "system"

    @field_validator("title_background", "title_text")
    @classmethod
    def _colour(cls, value, info):
        if value != "system" and not COLOUR.fullmatch(value):
            raise ValueError(f'{info.field_name} must be "system" or a colour like "#cc0000"')
        return value

    def colours(self):
        """(background, text) of title bars: "system" takes the desktop's focused
        title bar (platform.title_colours()), else the edge and
        text colours; system text that can't be read on the bar turns black or white."""
        system = platform.title_colours() or (EDGE, FG)
        background = self.title_background
        background = system[0] if background == "system" else background.lower()
        if self.title_text != "system":
            return background, self.title_text.lower()
        return background, readable(system[1], background)


# -- [[widgets]] ------------------------------------------------------------


def _component_settings(names, plugins):
    """{setting: type} that a widget's components declare."""
    declared = {}
    for name in names:
        if name in COMPONENTS:
            declared.update(COMPONENTS[name].settings)
        declared.update((plugins or {}).get(name) or {})
    return declared


class WidgetSpec(_Model):
    """A widget: one or more components in a window of its own, docked to the game
    (dock) or free on a monitor (screen, x, y); or one of a widgetwindow's widgets.

    Settings its components or named widget declare are allowed too (extras),
    checked against their declared types."""

    model_config = ConfigDict(frozen=True, extra="allow")

    components: tuple[str, ...]  # names
    dock: str | None = None  # one of DOCKS, or None for a free widget
    screen: str | None = None  # free widgets: monitor name; None = the whole desktop
    x: int = 0  # free: position on that monitor; docked: offset from the docked spot
    y: int = 0
    width: int | None = None  # None: the game's width (top/bottom) or what the components need
    height: int | None = None  # None: the game's height (left/right) or what they need
    layout: str = "compact"  # its text size: "compact" unless config.toml says "large"
    font_scale: float = 1.0
    show: str | None = None  # SHOW; default with_game when docked, always when free
    hide_empty: bool = False  # true: hide while its components (or plugin) have nothing to show
    id: str | None = None  # stable widget id (layout.toml); default "widget<n>:<first component>"
    widget: str | None = None  # the named widget it came from, if any
    window: str | None = None  # the widgetwindow it's in (#124); set by it, not a setting
    fill: bool = False  # in a widgetwindow: takes the height the others leave (height = "*")

    @property
    def shown(self):
        return self.show or ("with_game" if self.dock else "always")

    @property
    def extras(self):
        """The settings its components or named widget declared, as set."""
        return dict(self.model_extra or {})

    @model_validator(mode="before")
    @classmethod
    def _expand(cls, data):
        if not isinstance(data, dict):
            raise ValueError("must be a table")
        name = data.get("widget")
        if name is not None:
            named = WIDGETS.get(name)
            if named is None:
                raise ValueError(f"widget must be one of {', '.join(WIDGETS)}")
            data = {"id": named.name, **named.settings, **data}
            if named.titled:
                _check_titled(data.get("components"))
        if data.get("height") == "*":
            data = {**data, "height": None, "fill": True}
        if isinstance(data.get("components"), str):
            data = {**data, "components": [data["components"]]}
        return data

    @field_validator("components", mode="before")
    @classmethod
    def _components(cls, value, info):
        if not isinstance(value, (list, tuple)) or not value:
            raise ValueError("components must be a list of one or more names")
        if not all(isinstance(name, str) for name in value):
            raise ValueError("components must be names")
        plugins = (info.context or {}).get("plugins")
        if plugins is not None and len(value) > 1 and any(name in plugins for name in value):
            raise ValueError("a plugin must be the only component in its widget")
        if len(set(value)) < len(value):
            raise ValueError("each component can be in a widget only once")
        return value

    @field_validator("dock")
    @classmethod
    def _dock(cls, value):
        if value is not None:
            _choice("dock", value, DOCKS)
        return value

    @field_validator("x", "y", mode="before")
    @classmethod
    def _offset(cls, value, info):
        if not _whole(value):
            raise ValueError(f"{info.field_name} must be a whole number of pixels")
        return value

    @field_validator("width", "height", mode="before")
    @classmethod
    def _sizes(cls, value, info):
        return _pixels(info.field_name, value)

    @field_validator("layout")
    @classmethod
    def _layout(cls, value):
        return _choice("layout", value, tuple(LAYOUTS))

    @field_validator("font_scale", mode="before")
    @classmethod
    def _font_scale(cls, value):
        if not _positive(value):
            raise ValueError("font_scale must be a positive number")
        return value

    @field_validator("show")
    @classmethod
    def _show(cls, value):
        if value is not None:
            _choice("show", value, SHOW)
        return value

    @field_validator("hide_empty", mode="before")
    @classmethod
    def _hide_empty(cls, value):
        if not isinstance(value, bool):
            raise ValueError("hide_empty must be true or false")
        return value

    @field_validator("id")
    @classmethod
    def _id(cls, value):
        if value is not None and not WIDGET_ID.fullmatch(value):
            raise ValueError("id must be letters, digits, '_', '.', ':' or '-'")
        return value

    @model_validator(mode="after")
    def _declared(self, info):
        if self.fill and self.window is None:
            raise ValueError('height = "*" only works in a widgetwindow')
        if info.context is None:
            return self  # a copy the helper made (changed()): checked when it was read
        plugins = info.context.get("plugins")
        declared = _component_settings(self.components, plugins)
        declared.update(info.context.get("declared") or {})
        if self.widget in WIDGETS:
            declared.update(WIDGETS[self.widget].declared)
        for name, value in self.extras.items():
            kind = declared.get(name)
            if kind is None:
                raise ValueError(f"unknown setting {name}")
            if not setting_fits(kind, value):
                raise ValueError(f"{name} must be {SETTING_TYPES[kind]}")
        return self


def _check_titled(components):
    """Raises unless every component has a title (a tab label)."""
    if isinstance(components, str):
        components = [components]
    for name in components if isinstance(components, list | tuple) else ():
        if name in COMPONENTS and not COMPONENTS[name].title:
            titled = ", ".join(name for name, _ in web.tab_titles(COMPONENTS))
            raise ValueError(f"{name} has no title, so it can't be here; try {titled}")


# -- [[widgetwindows]] ------------------------------------------------------

PLACED = {"dock", "screen", "x", "y", "width", "window", "fill"}  # a widgetwindow sets these


class WindowSpec(_Model):
    """A widgetwindow (#124): a title bar over one or more widgets, stacked top to bottom.

    It docks to the game (DOCKS), to a monitor's edge ("screen:<monitor>:<edge>"),
    or floats on a monitor (dock None: screen, x, y, width and height).
    """

    id: str
    title: str
    dock: str | None = None  # DOCKS, "screen:<monitor>:<edge>", or None to float
    screen: str | None = None  # floating: the monitor's name
    x: int = 0  # floating: position on that monitor
    y: int = 0
    width: int | str | None = None  # px or "N%" of the monitor; None: the game's or monitor's
    height: int | str | None = None
    layout: str = "compact"  # its text size (and its widgets'), wherever it is
    font_scale: float = 1.0
    show: str | None = None  # SHOW; default with_game on the game, else always
    widgets: tuple[WidgetSpec, ...] = ()  # its widgets, in order, top to bottom

    @property
    def on_game(self):
        return self.dock in DOCKS

    @property
    def shown(self):
        return self.show or ("with_game" if self.on_game else "always")

    @model_validator(mode="before")
    @classmethod
    def _its_widgets(cls, data, info):
        """Its widgets take its id, its width (in pixels) and its text size; they
        can't place themselves, and at most one fills. From config.toml it needs
        at least one."""
        if not isinstance(data, dict):
            raise ValueError("must be a table")
        entries = data.get("widgets", ())
        if not isinstance(entries, list | tuple) or (info.context is not None and not entries):
            raise ValueError("widgets must be a list of widget tables")
        width = data.get("width") if _whole(data.get("width")) else None
        widgets, fills = [], 0
        for n, entry in enumerate(entries, start=1):
            if isinstance(entry, WidgetSpec):
                entry = entry.model_dump(exclude_unset=False) | (entry.model_extra or {})
            if not isinstance(entry, dict):
                raise ValueError(f"widget {n} must be a table")
            if entry.get("window") is None:  # from config.toml, not already its own
                placed = sorted(PLACED & set(entry))
                if placed:
                    fixed = ", ".join(placed)
                    raise ValueError(f"widget {n}: its widgetwindow places it: can't set {fixed}")
                entry = {"layout": data.get("layout", "compact"), **entry}
            fill = entry.get("height") == "*" or entry.get("fill") is True
            fills += fill
            # Its id even if that's missing (reported on its own), so they're still its.
            entry = {**entry, "width": width, "window": data.get("id") or "?", "dock": None}
            entry.pop("screen", None)
            widgets.append(entry)
        if fills > 1:
            raise ValueError('only one widget can have height = "*"')
        return {**data, "widgets": widgets}

    @field_validator("id")
    @classmethod
    def _id(cls, value):
        if not WIDGET_ID.fullmatch(value):
            raise ValueError("id must be letters, digits, '_', '.', ':' or '-'")
        return value

    @field_validator("title")
    @classmethod
    def _title(cls, value):
        if not value:
            raise ValueError("title must be some text")
        return value

    @field_validator("x", "y", mode="before")
    @classmethod
    def _offset(cls, value, info):
        if not _whole(value):
            raise ValueError(f"{info.field_name} must be a whole number of pixels")
        return value

    @field_validator("width", "height", mode="before")
    @classmethod
    def _size(cls, value, info):
        if value is not None and not _size(value):
            raise ValueError(f'{info.field_name} must be pixels or a percentage like "25%"')
        return value

    @field_validator("layout")
    @classmethod
    def _layout(cls, value):
        return _choice("layout", value, tuple(LAYOUTS))

    @field_validator("font_scale", mode="before")
    @classmethod
    def _font_scale(cls, value):
        if not _positive(value):
            raise ValueError("font_scale must be a positive number")
        return value

    @field_validator("show")
    @classmethod
    def _show(cls, value):
        if value is not None:
            _choice("show", value, SHOW)
        return value

    @model_validator(mode="after")
    def _placement(self):
        """Its placement and sizes fit together."""
        side = self.dock
        if side is None:
            if self.screen is None:
                raise ValueError("floating, it needs a screen (a monitor's name)")
            for name in ("width", "height"):
                if getattr(self, name) is None:
                    raise ValueError(f'{name} must be pixels or a percentage like "100%"')
            return self
        edge = SCREEN_DOCK.fullmatch(side)
        if side not in DOCKS and edge is None:
            docks = ", ".join(DOCKS)
            raise ValueError(f'dock must be one of {docks}, "screen:<monitor>:<edge>", or left out')
        if self.screen is not None or self.x or self.y:
            raise ValueError("docked, it can't set screen, x or y")
        sideways = side.endswith((":left", ":right"))
        across, other = ("width", "height") if sideways else ("height", "width")
        size = getattr(self, across)
        if edge is None and not (_whole(size) and size > 0):
            raise ValueError(f"{across} must be a whole number of pixels")
        if edge is not None and size is None:
            raise ValueError(f'{across} must be pixels or a percentage like "25%"')
        if getattr(self, other) is not None:
            whose = "the game's" if edge is None else "the monitor's"
            raise ValueError(f"docked to {side}, its other size is {whose}")
        return self


# -- the whole of config.toml ----------------------------------------------


class Settings(_Model):
    """config.toml: every table it may have."""

    window: WindowSettings = WindowSettings()
    theme: Theme = Theme()
    widgets: tuple[WidgetSpec, ...] = ()
    widgetwindows: tuple[WindowSpec, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _tables(cls, data):
        if not isinstance(data, dict):
            return data
        for n, entry in enumerate(data.get("widgets") or (), start=1):
            if isinstance(entry, dict):
                inner = sorted({"window", "fill"} & set(entry))
                if inner:
                    raise ValueError(f"widget {n}: unknown setting {inner[0]}")
        return data

    @model_validator(mode="after")
    def _unique_ids(self):
        seen = set()
        for window in self.widgetwindows:
            if window.id in seen:
                raise ValueError(f"two widgetwindows have the id {window.id!r}")
            seen.add(window.id)
        return self

    @property
    def all_widgets(self):
        """Every widget, those on their own first, then each widgetwindow's in order."""
        return self.widgets + tuple(w for window in self.widgetwindows for w in window.widgets)


TABLES = {
    "window": "[window]",
    "theme": "[theme]",
    "widgets": "[[widgets]]",
    "widgetwindows": "[[widgetwindows]]",
}


def _where(loc, numbers=None):
    """A pydantic error location as words: ("widgetwindows", 0, "widgets", 1, "height")
    -> "widgetwindow 1, widget 2", and the setting it's about, if any. numbers: the
    tables' numbers in the file, where some were left out (_leave_out_unknown)."""
    words, setting = [], None
    loc = list(loc)
    numbers = numbers or {}
    window = None  # the widgetwindow the location is inside, by its place in data
    while loc:
        part = loc.pop(0)
        if part in ("widgets", "widgetwindows") and loc and isinstance(loc[0], int):
            n = loc.pop(0)
            if part == "widgetwindows":
                window = n
                listed = [w for w, _ in numbers.get("widgetwindows", ())]
            elif window is not None:
                listed = dict(numbers.get("widgetwindows", ())).get(_nth(numbers, window), [])
            else:
                listed = numbers.get("widgets", [])
            words.append(f"{part[:-1]} {listed[n] if n < len(listed) else n + 1}")
        elif part in ("window", "theme") and not words:
            words.append(f"[{part}]")
        elif isinstance(part, str):
            setting = part
    return ", ".join(words), setting


def _nth(numbers, window):
    """The file's number for the widgetwindow at place window in data."""
    listed = [w for w, _ in numbers.get("widgetwindows", ())]
    return listed[window] if window < len(listed) else window + 1


def problems(error, path, numbers=None):
    """One message per mistake in a pydantic ValidationError, naming the file and table."""
    found = []
    for item in error.errors():
        where, setting = _where(item["loc"], numbers)
        kind, msg = item["type"], item["msg"].removeprefix("Value error, ")
        if kind == "extra_forbidden":
            known = ", ".join(TABLES.values())
            msg = (
                f"unknown table [{setting}] (config.toml has {known})"
                if not where
                else f"unknown setting {setting}"
            )
        elif kind == "missing":
            msg = f"{setting} is missing"
        elif kind not in ("value_error", "assertion_error") and setting:
            msg = f"{setting}: {msg}"
        found.append(f"{path}: {where}: {msg}" if where else f"{path}: {msg}")
    return found


def _known(names, plugins):
    return all(name in COMPONENTS or name in plugins for name in names)


def _leave_out_unknown(data, plugins):
    """(data without the widgets naming components, plugins or named widgets that
    aren't installed, a warning for each (#135: not a mistake), and the numbers in
    the file of the tables kept, for messages: {"widgets": [n, ...],
    "widgetwindows": [(w, [n, ...]), ...]})."""
    warnings = []
    numbers = {"widgets": [], "widgetwindows": []}

    def keep(entry, where):
        if not isinstance(entry, dict):
            return True
        name = entry.get("widget")
        if isinstance(name, str) and name not in WIDGETS:
            known = ", ".join(WIDGETS)
            warnings.append(
                f"{where}: no widget called {name!r} (there are {known}), so it's left out"
            )
            return False
        names = entry.get("components")
        names = [names] if isinstance(names, str) else names
        if isinstance(names, list) and all(isinstance(n, str) for n in names):
            missing = [n for n in names if not _known([n], plugins)]
            if missing:
                warnings.append(f"{where}: {', '.join(missing)} isn't installed, so it's left out")
                return False
        return True

    data = dict(data)
    if isinstance(data.get("widgets"), list):
        kept = [(n, e) for n, e in enumerate(data["widgets"], start=1) if keep(e, f"widget {n}")]
        data["widgets"] = [e for _, e in kept]
        numbers["widgets"] = [n for n, _ in kept]
    if isinstance(data.get("widgetwindows"), list):
        windows = []
        for w, window in enumerate(data["widgetwindows"], start=1):
            inside_numbers = []
            if isinstance(window, dict) and isinstance(window.get("widgets"), list):
                inside = [
                    (n, e)
                    for n, e in enumerate(window["widgets"], start=1)
                    if keep(e, f"widgetwindow {w}, widget {n}")
                ]
                if window["widgets"] and not inside:
                    why = "none of its widgets is installed, so it's left out"
                    warnings.append(f"widgetwindow {w}: {why}")
                    continue
                window = {**window, "widgets": [e for _, e in inside]}
                inside_numbers = [n for n, _ in inside]
            windows.append(window)
            numbers["widgetwindows"].append((w, inside_numbers))
        data["widgetwindows"] = windows
    return data, warnings, numbers


def read(path=paths.CONFIG, plugins=None):
    """(Settings, warnings) from config.toml (defaults if it isn't there).

    plugins: {name: {setting: type}} for every plugin found (#59); their names are
    components too, and their declared settings are allowed. Raises SettingsError
    listing every mistake.
    """
    plugins = plugins or {}
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise SettingsError([f"{path}: {exc}"]) from None
    data, warnings, numbers = _leave_out_unknown(data, plugins)
    warnings = [f"{path}: {warning}" for warning in warnings]
    try:
        settings = Settings.model_validate(data, context={"plugins": plugins})
    except ValidationError as error:
        raise SettingsError(problems(error, path, numbers), warnings) from None
    return settings, warnings


def load(path=paths.CONFIG, plugins=None):
    """read(), stopping the helper with every mistake listed if config.toml is wrong."""
    try:
        return read(path, plugins)
    except SettingsError as error:
        raise SystemExit("\n".join(error.problems)) from None


# -- layout.toml ------------------------------------------------------------


def load_layout(widgets, windows, path=paths.LAYOUT):
    """(widgets, windows, warnings): the model's layout (layout.Widget tuples) with
    layout.toml's saved changes on top, each spec checked by its model.

    The file is the helper's own: if any of it is wrong, none of it is used and
    each problem is a warning, so the layout is never half from the file (#135).
    Ids no longer in config.toml are ignored.
    """
    if not os.path.exists(path):
        return widgets, windows, []
    try:
        with open(path, "rb") as f:
            saved = tomllib.load(f).get("widgets", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return widgets, windows, [f"{path}: ignored: {exc}"]
    if not isinstance(saved, dict):
        return widgets, windows, [f"{path}: ignored: [widgets] must be a table of ids"]
    warnings = []

    def apply(items):
        result = []
        for item in items:
            values = saved.get(item.id)
            if values is None:
                result.append(item)
                continue
            where = f"{path}: {item.id}"
            if not isinstance(values, dict):
                warnings.append(f"{where}: must be a table")
                result.append(item)
                continue
            unknown = sorted(set(values) - set(SAVED))
            if unknown:
                warnings.append(f"{where}: unknown setting {', '.join(unknown)}")
            values = {k: (None if v == NONE else v) for k, v in values.items() if k in SAVED}
            is_open = values.pop("open", item.open)
            if not isinstance(is_open, bool):
                warnings.append(f"{where}: open must be true or false")
                is_open = item.open
            try:
                spec = item.spec.changed(**values)
            except ValidationError as error:
                warnings.extend(f"{where}: {p.split(': ', 2)[-1]}" for p in problems(error, path))
                spec = item.spec
            result.append(Widget(item.id, spec, is_open))
        return tuple(result)

    new_widgets, new_windows = apply(widgets), apply(windows)
    if warnings:
        return widgets, windows, [*warnings, f"{path}: ignored, so the layout is config.toml's"]
    return new_widgets, new_windows, []


def check(config_path=paths.CONFIG, layout_path=paths.LAYOUT, plugins=None):
    """Every problem and warning in config.toml and layout.toml, as messages, for
    `oolite-helper --check-config`. Empty when both are fine."""
    try:
        settings, warnings = read(config_path, plugins)
    except SettingsError as error:
        return [*error.warnings, *error.problems]
    try:
        widgets = widgets_from_specs(settings.all_widgets)
        windows = windows_from_specs(settings.widgetwindows, widgets)
    except SystemExit as error:
        return [*warnings, str(error)]
    return [*warnings, *load_layout(widgets, windows, layout_path)[2]]


# -- named widgets ----------------------------------------------------------


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
    declared: Any = None  # {setting: type} it understands beyond its components'

    def __post_init__(self):
        if self.declared is None:
            object.__setattr__(self, "declared", {})


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
    declared = declared_settings(path, settings.pop("settings", {}))
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
            _check_titled(settings.get("components"))
        context = {"plugins": {}, "declared": declared}
        spec = WidgetSpec.model_validate({**settings, "id": name}, context=context)
        spec = spec.model_copy(update={"widget": name})  # it isn't in WIDGETS yet
    except ValidationError as error:
        raise ValueError("\n".join(problems(error, path))) from None
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from None
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
        declared,
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


WIDGETS = {}  # filled below; WidgetSpec looks names up here when it's checked


def discover_widgets(folder=WIDGETS_DIR):
    """{name: NamedWidget} for every widget folder. A broken one is a bug: it raises."""
    if not os.path.isdir(folder):
        return {}
    return {
        name: read_widget(os.path.join(folder, name))
        for name in sorted(os.listdir(folder))
        if os.path.isfile(os.path.join(folder, name, "widget.toml"))
    }


WIDGETS.update(discover_widgets())
