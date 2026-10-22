"""Visualisations: each is a selector over the model plus a draw (#53).

A view picks exactly what it shows with select(model), usually from named
topics (helper/model.py TOPICS), and draws it in draw(value). The model calls
draw only when that value changes, so a view never lists the game fields it
depends on and can't miss an update. One view per thing that redraws: combine
topics in one selector rather than subscribing twice.

Views never change state. Clicks dispatch "ui/..." actions to the model;
purely local choices (a panel's own sort order) stay in the view, which then
calls self.refresh().

Left-click only, and no text fields: clicking a view must never take keyboard
focus from the game (verified on #20).
"""

from .base import View
from .style import Style

__all__ = ["Style", "View"]
