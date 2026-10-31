"""The layout: which widgets there are, where they go and whether they're open (#50).

Terms: a component renders part of the model; a widget hosts one or more
components; a widgetwindow holds one or more widgets under its own title; a
dock is a place beside the game window; the layout places every widget, in a
dock or free on a monitor.

Each [[widgets]] table in config.toml is a widget with a stable id: its `id`
setting, or "widget<n>:<first component>". The model keeps the widgets as its
`layout` topic, and only "layout/..." actions change them:

    {"type": "layout/move_widget", "id": "widget1:laptop", "x": 10, "y": 0}
    {"type": "layout/resize_widget", "id": "widget1:laptop", "width": 800, "height": 600}
    {"type": "layout/close_widget", "id": "widget1:laptop"}
    {"type": "layout/open_widget", "id": "widget1:laptop"}

config.toml stays the player's hand-written defaults. Changes made in the
helper are saved to layout.toml beside it, as differences from those
defaults; delete it to go back to config.toml. See docs/architecture.md,
"Layouts and the admin panel".
"""

import os
import sys
import tomllib
from dataclasses import dataclass, replace

from . import config

PATH = os.path.join(os.path.dirname(config.PATH), "layout.toml")
SAVED = ("x", "y", "width", "height", "open")  # what layout.toml may change


@dataclass(frozen=True)
class Widget:
    id: str
    spec: object  # widgets.WidgetSpec
    open: bool = True

    def setting(self, name):
        return self.open if name == "open" else getattr(self.spec, name)


def widgets_from_specs(specs):
    """The widgets for the configured widgets, in order. Ids must be unique."""
    widgets = []
    for n, spec in enumerate(specs, start=1):
        wid = spec.id or f"widget{n}:{spec.components[0]}"
        if any(widget.id == wid for widget in widgets):
            raise SystemExit(f"{config.PATH}: two widgets have the id {wid!r}")
        widgets.append(Widget(wid, spec))
    return tuple(widgets)


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
            return replace(widget, spec=replace(widget.spec, x=action["x"], y=action["y"]))
        if kind == "layout/resize_widget":
            size = {"width": action["width"], "height": action["height"]}
            return replace(widget, spec=replace(widget.spec, **size))
        if kind in ("layout/close_widget", "layout/open_widget"):
            return replace(widget, open=kind == "layout/open_widget")
        raise ValueError(f"unknown layout action {kind!r}")

    return tuple(change(widget) for widget in widgets)


def _valid(name, value):
    if name == "open":
        return isinstance(value, bool)
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return value > 0 if name in ("width", "height") else True


def load(widgets, path=PATH):
    """The widgets with layout.toml's saved changes applied.

    The file is the helper's own, so a bad one is reported and skipped rather
    than stopping the helper. Widgets no longer in config.toml are ignored.
    """
    if not os.path.exists(path):
        return widgets
    try:
        with open(path, "rb") as f:
            saved = tomllib.load(f).get("widgets", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"oolite-helper: ignoring {path}: {exc}", file=sys.stderr)
        return widgets
    changed = []
    for widget in widgets:
        values = saved.get(widget.id)
        if isinstance(values, dict):
            good = {k: v for k, v in values.items() if k in SAVED and _valid(k, v)}
            is_open = good.pop("open", widget.open)
            widget = replace(widget, spec=replace(widget.spec, **good), open=is_open)
        changed.append(widget)
    return tuple(changed)


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
            if widget.setting(name) != default.setting(name) and widget.setting(name) is not None
        }
        if changed:
            diffs[widget.id] = changed
    return diffs


def _toml(value):
    return ("true" if value else "false") if isinstance(value, bool) else str(value)


class LayoutFile:
    """Saves the layout's differences from config.toml to layout.toml."""

    def __init__(self, defaults, path=PATH):
        self.defaults = defaults
        self.path = path

    def save(self, widgets):
        diffs = differences(self.defaults, widgets)
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
