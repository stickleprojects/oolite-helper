"""The main body: key panels, All keys, the trade table and detail, Trade here."""

import tkinter as tk

from ..browser import sort_rows
from ..contexts import ACTION_NOTES, ALL_KEY_GROUPS
from ..trade import ECONOMIES, GOVERNMENTS
from .base import View
from .style import ACCENT, BG, DIM, FG, GREEN, MONO, PANEL, RED, SANS
from .trade_here import advice_panel

# Trade table columns: (sort key, title, sorted high-to-low on the first click)
TRADE_COLUMNS = (
    ("commodity", "Commodity", False),
    ("here", "Here", True),
    ("best", "Best in range", True),
    ("where", "Where", False),
    ("margin", "Margin", True),
)


class Body(View):
    """Whatever the visible tab shows. Rebuilt only when its value changes."""

    def __init__(self, model, style, frame):
        self.frame = frame
        for c in range(style.columns):
            frame.columnconfigure(c, weight=1, uniform="col")
        self.group = 0  # group shown on the All keys tab (local to this view)
        self.sort = ("margin", True)  # trade table column, high-to-low (local)
        super().__init__(model, style)

    def select(self, model):
        tab = model.topic("tab")
        if tab == "trade" and model.ui.commodity:
            detail = model.topic("trade_detail")
            return ("detail", *detail) if detail else None
        if tab == "trade":
            return (
                "trade",
                self.sort,
                tuple(sort_rows(list(model.topic("trade_rows")), *self.sort)),
                model.topic("market_advice"),  # Trade here, while docked
            )
        if not model.keymap:
            return None
        if tab == "all":
            return ("all", self.group)
        return ("keys", model.topic("sections"))

    def draw(self, wanted):
        for child in self.frame.winfo_children():
            child.destroy()
        if wanted and wanted[0] == "trade":
            self.draw_trade(wanted[2], wanted[3])
        elif wanted and wanted[0] == "detail":
            self.draw_detail(*wanted[1:])
        elif wanted and wanted[0] == "all":
            self.draw_all_keys(self.group)
        elif wanted:
            self.draw_sections(*wanted[1:])

    # -- clicks ------------------------------------------------------------

    def choose_group(self, index):
        self.group = index
        self.refresh()

    def sort_trade(self, key, high_first):
        column, descending = self.sort
        self.sort = (key, not descending) if column == key else (key, high_first)
        self.refresh()

    def open_commodity(self, commodity):
        self.dispatch({"type": "ui/open_commodity", "commodity": commodity})

    def choose_destination(self, system_id):
        self.dispatch({"type": "ui/choose_destination", "system": system_id})

    def change_quantity(self, quantity):
        self.dispatch({"type": "ui/change_quantity", "quantity": quantity})

    # -- drawing -----------------------------------------------------------

    def draw_trade(self, rows, advice=()):
        """Trade here (while docked), then each commodity's price here against the
        best price within fuel range."""
        if advice:
            self.draw_advice(advice)
        panel = tk.Frame(self.frame, bg=PANEL, padx=self.style.px(18), pady=self.style.px(12))
        panel.grid(
            row=1 if advice else 0,
            column=0,
            columnspan=self.style.columns,
            sticky="new",
            padx=self.style.px(12),
            pady=self.style.px(12),
        )
        if not rows:
            tk.Label(
                panel,
                text="No market data yet. Dock at a station, or wait for the systems in "
                "fuel range to arrive.",
                font=self.style.font(SANS, 18),
                fg=DIM,
                bg=PANEL,
            ).grid(row=0, column=0, sticky="w")
            return
        column, descending = self.sort
        for c, (key, title, high_first) in enumerate(TRADE_COLUMNS):
            arrow = (" ▼" if descending else " ▲") if key == column else ""
            header = tk.Label(
                panel,
                text=title + arrow,
                font=self.style.font(SANS, 16, "bold"),
                fg=ACCENT if key == column else DIM,
                bg=PANEL,
            )
            header.grid(
                row=0, column=c, sticky="w", padx=self.style.px(0, 28), pady=self.style.px(0, 6)
            )
            # Left-click only, like the tabs: focus stays with the game.
            header.bind("<Button-1>", lambda e, k=key, h=high_first: self.sort_trade(k, h))
        for r, row in enumerate(rows, start=1):
            name = self.model.commodity_name(row.commodity) + ("  illegal" if row.illegal else "")
            margin = row.margin
            cells = (
                (name, RED if row.illegal else FG, SANS),
                (
                    _price(row.here, row.here_note if row.stock else "none"),
                    FG if row.stock else DIM,
                    MONO,
                ),
                (_price(row.best, row.best_note), FG, MONO),
                (_where(row), FG, SANS),
                (
                    "" if margin is None else f"{margin / 10:+.1f}",
                    GREEN if margin and margin > 0 else DIM,
                    MONO,
                ),
            )
            for c, (text, colour, family) in enumerate(cells):
                cell = tk.Label(
                    panel, text=text, font=self.style.font(family, 18), fg=colour, bg=PANEL
                )
                cell.grid(row=r, column=c, sticky="w", padx=self.style.px(0, 28))
                cell.bind("<Button-1>", lambda e, k=row.commodity: self.open_commodity(k))
        tk.Label(
            panel,
            text="Click a commodity for every system in range, a quantity and the keys to press.",
            font=self.style.font(SANS, 14),
            fg=DIM,
            bg=PANEL,
        ).grid(
            row=len(rows) + 1,
            column=0,
            columnspan=len(TRADE_COLUMNS),
            sticky="w",
            pady=self.style.px(8, 0),
        )

    def draw_detail(self, commodity, row, offers, offer, limit, quantity, steps):
        """One commodity: every system in range, a quantity picker and the keys to press."""
        panel = tk.Frame(self.frame, bg=PANEL, padx=self.style.px(18), pady=self.style.px(12))
        panel.grid(
            row=0,
            column=0,
            columnspan=self.style.columns,
            sticky="new",
            padx=self.style.px(12),
            pady=self.style.px(12),
        )
        name = self.model.commodity_name(commodity)
        unit = row.unit if row else "t"
        top = tk.Frame(panel, bg=PANEL)
        top.pack(fill="x", anchor="w")
        back = tk.Label(
            top, text="◀ All commodities", font=self.style.font(SANS, 16), fg=ACCENT, bg=PANEL
        )
        back.pack(side="left", padx=self.style.px(0, 28))
        back.bind("<Button-1>", lambda e: self.open_commodity(None))
        here = ""
        if row and row.here is not None:
            here = f"here {_price(row.here, row.here_note)}, {row.stock or 0} {unit} on sale"
        tk.Label(
            top,
            text=f"{name}{'  illegal here' if row and row.illegal else ''}   {here}",
            font=self.style.font(SANS, 20, "bold"),
            fg=RED if row and row.illegal else FG,
            bg=PANEL,
        ).pack(side="left")

        table = tk.Frame(panel, bg=PANEL)
        table.pack(fill="x", anchor="w", pady=self.style.px(10, 0))
        if not offers:
            tk.Label(
                table,
                text="No prices for systems in fuel range yet.",
                font=self.style.font(SANS, 18),
                fg=DIM,
                bg=PANEL,
            ).grid(row=0, column=0, sticky="w")
        titles = ("Sell at", "Price", "Margin", "Distance", "Economy", "Government")
        for c, title in enumerate(titles if offers else ()):
            tk.Label(
                table, text=title, font=self.style.font(SANS, 16, "bold"), fg=DIM, bg=PANEL
            ).grid(row=0, column=c, sticky="w", padx=self.style.px(0, 28), pady=self.style.px(0, 6))
        for r, o in enumerate(offers, start=1):
            chosen = o is offer
            margin = o.price - row.here if row and row.here is not None else None
            government = _name(GOVERNMENTS, o.government) + (" ⚠" if o.dangerous else "")
            cells = (
                (("▶ " if chosen else "  ") + o.name + ("  illegal" if o.illegal else ""), SANS),
                (_price(o.price, o.note), MONO),
                ("" if margin is None else f"{margin / 10:+.1f}", MONO),
                ("" if o.distance is None else f"{o.distance:.1f} ly", MONO),
                (_name(ECONOMIES, o.economy), SANS),
                (government, SANS),
            )
            for c, (text, family) in enumerate(cells):
                colour = ACCENT if chosen else FG
                if c == 0 and o.illegal or c == 5 and o.dangerous:
                    colour = RED
                elif c == 2 and margin is not None:
                    colour = GREEN if margin > 0 else DIM
                cell = tk.Label(
                    table, text=text, font=self.style.font(family, 18), fg=colour, bg=PANEL
                )
                cell.grid(row=r, column=c, sticky="w", padx=self.style.px(0, 28))
                cell.bind("<Button-1>", lambda e, i=o.system_id: self.choose_destination(i))

        picker = tk.Frame(panel, bg=PANEL)
        picker.pack(fill="x", anchor="w", pady=self.style.px(14, 0))
        tk.Label(picker, text="Buy", font=self.style.font(SANS, 18, "bold"), fg=DIM, bg=PANEL).pack(
            side="left", padx=self.style.px(0, 14)
        )
        for text, value in (
            ("−10", quantity - 10),
            ("−1", quantity - 1),
            (f"{quantity} {unit}", None),
            ("+1", quantity + 1),
            ("+10", quantity + 10),
            ("Max", limit.most),
        ):
            button = tk.Label(
                picker,
                text=f" {text} ",
                font=self.style.font(MONO if value is None else SANS, 18, "bold"),
                fg=ACCENT if value is None else FG,
                bg=PANEL if value is None else BG,
            )
            button.pack(side="left", padx=self.style.px(0, 8))
            if value is not None:
                v = max(0, min(value, limit.most))
                button.bind("<Button-1>", lambda e, v=v: self.change_quantity(v))
        tk.Label(
            picker,
            text=f"most {limit.most} ({limit.reason})",
            font=self.style.font(SANS, 16),
            fg=DIM,
            bg=PANEL,
        ).pack(side="left", padx=self.style.px(14, 0))

        summary = []
        if row and row.here is not None:
            summary.append(f"Cost {quantity * row.here / 10:.1f} cr")
            summary.append(f"cargo {quantity} {unit}")
            if offer is not None:
                profit = quantity * (offer.price - row.here) / 10
                summary.append(f"profit at {offer.name} {profit:+.1f} cr")
        if summary:
            tk.Label(
                panel, text="    ".join(summary), font=self.style.font(SANS, 18), fg=FG, bg=PANEL
            ).pack(anchor="w", pady=self.style.px(8, 0))

        for i, step in enumerate(steps, start=1):
            tk.Label(
                panel,
                text=f"{i}. {step}",
                font=self.style.font(SANS, 18),
                fg=FG,
                bg=PANEL,
                justify="left",
                wraplength=self.style.desc_wrap * self.style.columns,
            ).pack(anchor="w", pady=self.style.px(8 if i == 1 else 2, 0))

    def draw_sections(self, wanted):
        for i, (title, actions) in enumerate(wanted):
            row, column = i // self.style.columns, i % self.style.columns
            self.draw_panel(self.frame, row, column, title, actions)

    def draw_advice(self, groups):
        """The Trade here panel, across the top of the body."""
        panel = advice_panel(
            self.frame, self.style, groups, self.style.desc_wrap * self.style.columns
        )
        panel.grid(
            row=0,
            column=0,
            columnspan=self.style.columns,
            sticky="new",
            padx=self.style.px(12),
            pady=self.style.px(12),
        )

    def draw_all_keys(self, current):
        """The game's key groups as clickable chips, and the chosen group's keys."""
        chips = tk.Frame(self.frame, bg=BG)
        chips.grid(
            row=0,
            column=0,
            columnspan=self.style.columns,
            sticky="w",
            padx=self.style.px(12),
            pady=self.style.px(4, 0),
        )
        per_line = 7
        line = None
        for i, (header, _) in enumerate(ALL_KEY_GROUPS):
            if i % per_line == 0:
                line = tk.Frame(chips, bg=BG)
                line.pack(anchor="w")
            active = i == current
            chip = tk.Label(
                line,
                text=f" {self.model.keymap.describe(header)} ",
                font=self.style.font(SANS, 14),
                fg=BG if active else FG,
                bg=ACCENT if active else PANEL,
            )
            chip.pack(side="left", padx=self.style.px(0, 8), pady=self.style.px(4))
            chip.bind("<Button-1>", lambda e, i=i: self.choose_group(i))
        header, actions = ALL_KEY_GROUPS[current]
        panel = self.draw_panel(
            self.frame, 1, 0, self.model.keymap.describe(header), actions, show_unbound=True
        )
        panel.grid(columnspan=self.style.columns)

    def draw_panel(self, parent, row, column, title, actions, show_unbound=False):
        panel = tk.Frame(parent, bg=PANEL, padx=self.style.px(18), pady=self.style.px(12))
        panel.grid(
            row=row, column=column, sticky="new", padx=self.style.px(12), pady=self.style.px(12)
        )
        if title:
            tk.Label(
                panel,
                text=title.upper(),
                font=self.style.font(SANS, 16, "bold"),
                fg=DIM,
                bg=PANEL,
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=self.style.px(0, 6))
        row = 1
        for action in actions:
            keys = self.model.keymap.keys(action)
            if not keys and not show_unbound:
                continue  # unbound in this setup
            tk.Label(
                panel,
                text=keys or "—",
                font=self.style.font(MONO, 20, "bold"),
                fg=ACCENT if keys else DIM,
                bg=PANEL,
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=self.style.px(0, 18))
            text = self.model.keymap.describe(action)
            if action in ACTION_NOTES:
                text += f" ({ACTION_NOTES[action]})"
            tk.Label(
                panel,
                text=text,
                font=self.style.font(SANS, 20),
                fg=FG if keys else DIM,
                bg=PANEL,
                anchor="w",
                justify="left",
                wraplength=self.style.desc_wrap,
            ).grid(row=row, column=1, sticky="w")
            row += 1
        return panel


def _price(decicredits, note):
    if decicredits is None:
        return "—"
    text = f"{decicredits / 10:.1f}"
    return f"{text} ({note})" if note else text


def _name(names, index):
    return names[index] if isinstance(index, int) and 0 <= index < len(names) else "?"


def _where(row):
    if not row.where:
        return ""
    return f"{row.where} {row.distance:.1f} ly" if row.distance is not None else row.where
