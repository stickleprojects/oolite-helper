"""The tab row: tabs on the left; clearance badge and TORUS/JUMP chips on the right."""

import tkinter as tk

from .base import Component
from .style import ACCENT, BG, DIM, GREEN, PANEL, RED, SANS

TABS = ("keys", "all_keys", "trade_table")  # web component names; titles from them


class Tabs(Component):
    def __init__(self, model, style, parent):
        from ...plugin_api import tabs  # late: plugin_api imports helper.tk.components

        titles = dict(tabs())
        self.labels = {}
        for name in TABS:
            title = titles[name]
            label = tk.Label(parent, text=f"  {title}  ", font=style.font(SANS, 16, "bold"), bg=BG)
            label.pack(side="left", padx=style.px(0, 12))
            # Left-click only: clicking never moves keyboard focus off the game (#20).
            label.bind("<Button-1>", lambda e, name=name: self.choose(name))
            self.labels[name] = label
        super().__init__(model, style)

    def choose(self, name):
        self.dispatch({"type": "ui/choose_tab", "tab": name})

    def select(self, model):
        return model.topic("tab")

    def draw(self, tab):
        for name, label in self.labels.items():
            active = name == tab
            label.config(fg=BG if active else DIM, bg=ACCENT if active else PANEL)


class DriveChips(Component):
    """TORUS ✓/✗ and JUMP ✓/✗ while flying."""

    def __init__(self, model, style, parent):
        self.labels = {}
        for name in ("JUMP", "TORUS"):
            label = tk.Label(parent, font=style.font(SANS, 16, "bold"), bg=BG)
            label.pack(side="right", padx=style.px(12, 0))
            self.labels[name] = label
        super().__init__(model, style)

    def select(self, model):
        return model.topic("indicators")

    def draw(self, indicators):
        self.empty = not indicators
        shown = {name: (ok, why) for name, ok, why in indicators}
        for name, label in self.labels.items():
            if name not in shown:
                label.config(text="", bg=BG)
                continue
            ok, why = shown[name]
            text = f"  {name} ✓  " if ok else f"  {name} ✗ {why}  "
            label.config(text=text, fg=BG, bg=GREEN if ok else RED)


class ClearanceBadge(Component):
    """Docking clearance near a station (#1); "timing out" blinks."""

    def __init__(self, model, style, parent):
        self.label = tk.Label(parent, font=style.font(SANS, 16, "bold"), bg=BG)
        self.label.pack(side="right", padx=style.px(12, 0))
        super().__init__(model, style)

    def select(self, model):
        badge = model.topic("clearance")
        # Only a blinking badge needs the clock, so the others don't redraw with it.
        blink = model.topic("clock") % 2 if badge and badge[2] else 0
        return badge, blink

    def draw(self, value):
        badge, blink = value
        self.empty = badge is None
        if badge is None:
            self.label.config(text="", bg=BG)
            return
        text, colour, _ = badge
        bg = PANEL if blink else {"green": GREEN, "amber": ACCENT, "red": RED}[colour]
        self.label.config(text=f"  {text}  ", fg=ACCENT if blink else BG, bg=bg)
