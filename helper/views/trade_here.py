"""Trade here: your hold, prices against the last market, and the best buys (#20)."""

import tkinter as tk

from .base import View
from .style import ACCENT, DIM, FG, PANEL, RED, SANS


def advice_panel(parent, style, groups, wrap):
    """A panel with one heading per group, then its lines. The caller places it."""
    panel = tk.Frame(parent, bg=PANEL, padx=style.px(18), pady=style.px(12))
    tk.Label(panel, text="TRADE HERE", font=style.font(SANS, 16, "bold"), fg=DIM, bg=PANEL).pack(
        anchor="w"
    )
    for heading, lines in groups:
        tk.Label(panel, text=heading, font=style.font(SANS, 18, "bold"), fg=ACCENT, bg=PANEL).pack(
            anchor="w", pady=style.px(8, 0)
        )
        for line in lines:
            tk.Label(
                panel,
                text=line,
                font=style.font(SANS, 18),
                fg=RED if "illegal" in line else FG,
                bg=PANEL,
                justify="left",
                wraplength=wrap,
            ).pack(anchor="w")
    return panel


class TradeHere(View):
    """Trade here on its own, e.g. in a widget docked beside the game (#50)."""

    def __init__(self, model, style, parent):
        self.parent = parent
        self.panel = None
        super().__init__(model, style)

    def select(self, model):
        return model.topic("market_advice")

    def draw(self, groups):
        if self.panel is not None:
            self.panel.destroy()
        if not groups:
            groups = (("Dock at a station for trade advice.", ()),)
        self.panel = advice_panel(self.parent, self.style, groups, self.style.width - 40)
        self.panel.pack(fill="both", expand=True)
