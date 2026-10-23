"""The layout: which panels there are, where they go and whether they're open (#50).

Each [[widgets]] table in config.toml is a panel with a stable id: its `id`
setting, or "widget<n>:<first view>". The model keeps the panels as its
`layout` topic, and only "layout/..." actions change them:

    {"type": "layout/move_panel", "id": "widget1:laptop", "x": 10, "y": 0}
    {"type": "layout/resize_panel", "id": "widget1:laptop", "width": 800, "height": 600}
    {"type": "layout/close_panel", "id": "widget1:laptop"}
    {"type": "layout/open_panel", "id": "widget1:laptop"}

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
class Panel:
    id: str
    spec: object  # widgets.WidgetSpec
    open: bool = True

    def setting(self, name):
        return self.open if name == "open" else getattr(self.spec, name)


def panels_from_specs(specs):
    """The panels for the configured widgets, in order. Ids must be unique."""
    panels = []
    for n, spec in enumerate(specs, start=1):
        pid = spec.id or f"widget{n}:{spec.views[0]}"
        if any(panel.id == pid for panel in panels):
            raise SystemExit(f"{config.PATH}: two widgets have the id {pid!r}")
        panels.append(Panel(pid, spec))
    return tuple(panels)


def find(panels, pid):
    """The panel with this id, or None."""
    return next((panel for panel in panels if panel.id == pid), None)


def reduce_layout(panels, action):
    """The layout reducer: new panels for a "layout/..." action."""
    kind, pid = action["type"], action.get("id")
    if find(panels, pid) is None:
        raise ValueError(f"{kind}: no panel {pid!r}")

    def change(panel):
        if panel.id != pid:
            return panel
        if kind == "layout/move_panel":
            return replace(panel, spec=replace(panel.spec, x=action["x"], y=action["y"]))
        if kind == "layout/resize_panel":
            size = {"width": action["width"], "height": action["height"]}
            return replace(panel, spec=replace(panel.spec, **size))
        if kind in ("layout/close_panel", "layout/open_panel"):
            return replace(panel, open=kind == "layout/open_panel")
        raise ValueError(f"unknown layout action {kind!r}")

    return tuple(change(panel) for panel in panels)


def _valid(name, value):
    if name == "open":
        return isinstance(value, bool)
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return value > 0 if name in ("width", "height") else True


def load(panels, path=PATH):
    """The panels with layout.toml's saved changes applied.

    The file is the helper's own, so a bad one is reported and skipped rather
    than stopping the helper. Panels no longer in config.toml are ignored.
    """
    if not os.path.exists(path):
        return panels
    try:
        with open(path, "rb") as f:
            saved = tomllib.load(f).get("panels", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"oolite-helper: ignoring {path}: {exc}", file=sys.stderr)
        return panels
    changed = []
    for panel in panels:
        values = saved.get(panel.id)
        if isinstance(values, dict):
            good = {k: v for k, v in values.items() if k in SAVED and _valid(k, v)}
            is_open = good.pop("open", panel.open)
            panel = replace(panel, spec=replace(panel.spec, **good), open=is_open)
        changed.append(panel)
    return tuple(changed)


def differences(defaults, panels):
    """{panel id: {setting: value}} where panels differ from defaults (config.toml)."""
    diffs = {}
    for panel in panels:
        default = find(defaults, panel.id)
        if default is None:
            continue
        changed = {
            name: panel.setting(name)
            for name in SAVED
            if panel.setting(name) != default.setting(name) and panel.setting(name) is not None
        }
        if changed:
            diffs[panel.id] = changed
    return diffs


def _toml(value):
    return ("true" if value else "false") if isinstance(value, bool) else str(value)


class LayoutFile:
    """Saves the layout's differences from config.toml to layout.toml."""

    def __init__(self, defaults, path=PATH):
        self.defaults = defaults
        self.path = path

    def save(self, panels):
        diffs = differences(self.defaults, panels)
        if not diffs:
            if os.path.exists(self.path):
                os.remove(self.path)
            return
        lines = [
            "# Written by oolite-helper: panels moved, resized or closed in the helper.",
            "# Delete this file to go back to the [[widgets]] in config.toml.",
        ]
        for pid, values in diffs.items():
            lines += ["", f'[panels."{pid}"]']
            lines += [f"{name} = {_toml(value)}" for name, value in values.items()]
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, self.path)
