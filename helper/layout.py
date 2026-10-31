"""The layout: which widgets there are, where they go and whether they're open (#50).

Terms: a component renders part of the model; a widget hosts one or more
components; a widgetwindow holds one or more widgets under its own title; a
dock is a place beside the game window; the layout places every widget, in a
dock or free on a monitor.

Each [[widgets]] table in config.toml is a widget with a stable id: its `id`
setting, or "widget<n>:<first component>". The model keeps the widgets as its
`layout` topic, and only "layout/..." actions change them:

    {"type": "layout/move_widget", "id": "widget1:laptop", "x": 10, "y": 0}
    {"type": "layout/move_widget", "id": "trading", "dock": None, "screen": "eDP-1",
     "x": 10, "y": 0, "width": 600, "height": 400}  # a whole new placement (#124)
    {"type": "layout/resize_widget", "id": "widget1:laptop", "width": 800, "height": 600}
    {"type": "layout/resize_widget", "id": "trading", "width": 700}  # either or both
    {"type": "layout/close_widget", "id": "widget1:laptop"}
    {"type": "layout/open_widget", "id": "widget1:laptop"}

Widgetwindows (#124) are kept the same way, by their ids, in the model's
`windows` topic; the same actions change them.

config.toml stays the player's hand-written defaults. Changes made in the
helper are saved to layout.toml beside it, as differences from those
defaults; delete it to go back to config.toml. settings.load_layout reads it
back, checked by the settings models (#135). See docs/architecture.md,
"Layouts and the admin panel".
"""

import json
import os
from dataclasses import dataclass, replace

from . import paths

SAVED = ("x", "y", "width", "height", "open", "dock", "screen")  # what layout.toml may change
NONE = "none"  # layout.toml's word for an unset dock, screen or size (TOML has no null)
MOVED = ("x", "y", "dock", "screen", "width", "height")  # what layout/move_widget may set


@dataclass(frozen=True)
class Widget:
    id: str
    spec: object  # settings.WidgetSpec, or settings.WindowSpec for a widgetwindow
    open: bool = True

    def setting(self, name):
        return self.open if name == "open" else getattr(self.spec, name)


def widgets_from_specs(specs):
    """The widgets for the configured widgets, in order. Ids must be unique."""
    widgets = []
    for n, spec in enumerate(specs, start=1):
        wid = spec.id or f"widget{n}:{spec.components[0]}"
        if any(widget.id == wid for widget in widgets):
            raise SystemExit(f"{paths.CONFIG}: two widgets have the id {wid!r}")
        widgets.append(Widget(wid, spec))
    return tuple(widgets)


def windows_from_specs(specs, widgets=()):
    """The widgetwindows (#124), by id. Ids mustn't clash with each other or widgets'."""
    taken = {widget.id for widget in widgets}
    for spec in specs:
        if spec.id in taken:
            raise SystemExit(f"{paths.CONFIG}: a widget and a widgetwindow have the id {spec.id!r}")
        taken.add(spec.id)
    return tuple(Widget(spec.id, spec) for spec in specs)


def find(widgets, wid):
    """The widget with this id, or None."""
    return next((widget for widget in widgets if widget.id == wid), None)


def reduce_layout(widgets, action):
    """The layout reducer: new widgets for a "layout/..." action."""
    kind, wid = action["type"], action.get("id")
    if find(widgets, wid) is None:
        raise ValueError(f"{kind}: no widget {wid!r}")

    def change(widget):
        if widget.id != wid:
            return widget
        if kind == "layout/move_widget":
            moved = {name: action[name] for name in MOVED if name in action}
            return replace(widget, spec=widget.spec.changed(**moved))
        if kind == "layout/resize_widget":
            size = {name: action[name] for name in ("width", "height") if name in action}
            return replace(widget, spec=widget.spec.changed(**size))
        if kind in ("layout/close_widget", "layout/open_widget"):
            return replace(widget, open=kind == "layout/open_widget")
        raise ValueError(f"unknown layout action {kind!r}")

    return tuple(change(widget) for widget in widgets)


def differences(defaults, widgets):
    """{widget id: {setting: value}} where widgets differ from defaults (config.toml)."""
    diffs = {}
    for widget in widgets:
        default = find(defaults, widget.id)
        if default is None:
            continue
        changed = {
            name: widget.setting(name)
            for name in SAVED
            if widget.setting(name) != default.setting(name)
        }
        if changed:
            diffs[widget.id] = changed
    return diffs


def _toml(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return json.dumps(NONE)
    return json.dumps(value) if isinstance(value, str) else str(value)


class LayoutFile:
    """Saves the layout's differences from config.toml to layout.toml."""

    def __init__(self, defaults, path=paths.LAYOUT, window_defaults=(), widgets=(), windows=()):
        """widgets and windows: the layout as it is now (loaded), kept when only
        the other changes."""
        self.defaults = tuple(defaults) + tuple(window_defaults)
        self.path = path
        self.widgets, self.windows = tuple(widgets), tuple(windows)

    def save(self, widgets):
        self.widgets = tuple(widgets)
        self._write()

    def save_windows(self, windows):
        self.windows = tuple(windows)
        self._write()

    def _write(self):
        diffs = differences(self.defaults, self.widgets + self.windows)
        if not diffs:
            if os.path.exists(self.path):
                os.remove(self.path)
            return
        lines = [
            "# Written by oolite-helper: widgets moved, resized or closed in the helper.",
            "# Delete this file to go back to the [[widgets]] in config.toml.",
        ]
        for wid, values in diffs.items():
            lines += ["", f'[widgets."{wid}"]']
            lines += [f"{name} = {_toml(value)}" for name, value in values.items()]
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, self.path)
