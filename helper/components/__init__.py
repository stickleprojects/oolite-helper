"""Visualisations: each is a selector over the model plus a draw (#53).

A component picks exactly what it shows with select(model), usually from named
topics (helper/model.py TOPICS), and draws it in draw(value). The model calls
draw only when that value changes, so a component never lists the game fields it
depends on and can't miss an update. One component per thing that redraws: combine
topics in one selector rather than subscribing twice.

Components never change state. Clicks dispatch "ui/..." actions to the model;
purely local choices (a panel's own sort order) stay in the component, which then
calls self.refresh().

Left-click only, and no text fields: clicking a component must never take keyboard
focus from the game (verified on #20).
"""

from .base import Component
from .style import Style

__all__ = ["Style", "Component"]
