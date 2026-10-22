"""The helper window."""

import argparse
import fcntl
import json
import os
import sys
import tempfile
import tkinter as tk
import traceback

from . import config
from .browser import (
    buy_limit,
    commodity_offers,
    commodity_rows,
    held,
    sort_rows,
    trade_steps,
)
from .contexts import ACTION_NOTES, ALL_KEY_GROUPS, indicators, sections, tip
from .keys import commodity_fallback, load_keymap
from .markets import MarketStore
from .screen import ANCHORS, choose_monitor, geometry, list_monitors
from .sources import DEFAULT_LOG, LogSource
from .state import GameState
from .trade import ECONOMIES, GOVERNMENTS

POLL_MS = 200
COLUMN_WIDTH = 600  # px a key panel needs at text scale 1.0
# Layouts: text and spacing scale (multiplied by font_scale) and most key columns.
LAYOUTS = {
    "large": (1.0, 3),
    "compact": (0.6, 6),
}
BG = "#101418"
PANEL = "#171d23"
FG = "#e6e6e6"
ACCENT = "#ffb000"
RED = "#ff4040"
DIM = "#7a8590"
SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

TABS = (("keys", "Keys"), ("all", "All keys"), ("trade", "Trade"))
# Trade table columns: (sort key, title, sorted high-to-low on the first click)
TRADE_COLUMNS = (
    ("commodity", "Commodity", False),
    ("here", "Here", True),
    ("best", "Best in range", True),
    ("where", "Where", False),
    ("margin", "Margin", True),
)
GREEN = "#5fd068"
# Contexts that switch the view back to Keys whatever tab is chosen; the chosen
# tab comes back when they end.
URGENT = ("red alert", "jump countdown", "ship destroyed")


def should_quit_for_messages(messages, first_poll, quit_with_game=True):
    """Whether a close message is a live exit rather than old log replay."""
    replay = first_poll or any(m.get("type") == "session" for m in messages)
    return quit_with_game and not replay and any(m.get("type") == "closed" for m in messages)


class HelperWindow:
    def __init__(self, root, source, geometry, quit_with_game=True, font_scale=1.0, layout="large"):
        self.root = root
        self.source = source
        self.quit_with_game = quit_with_game
        layout_scale, max_columns = LAYOUTS[layout]
        self.scale = layout_scale * font_scale
        width = int(geometry.split("x", 1)[0])
        self.columns = max(1, min(max_columns, int(width / (COLUMN_WIDTH * self.scale))))
        self.desc_wrap = int(width / self.columns * 0.6)
        self.first_poll = True
        self.state = GameState()
        self.market_store = MarketStore()
        self.notice = self.market_store.load_error  # shown until the game sends something
        self.shown_market_age = None
        self.shown = None  # what the body currently shows
        self.tab = "keys"  # the tab the player chose
        self.all_group = 0  # group shown on the All keys tab
        self.trade_sort = ("margin", True)  # column, high-to-low
        self.trade_commodity = None  # commodity open in the detail view
        self.trade_destination = None  # system id chosen there; None = the best price
        self.trade_quantity = None  # units chosen there; None = the most you can buy
        self.last_message = ""
        self.error = None  # last unexpected error, shown until messages flow again

        try:
            self.keymap = load_keymap()
            self.keymap_error = None
        except Exception as e:  # show the problem instead of dying
            self.keymap = None
            self.keymap_error = f"Couldn't read the game's key settings: {e}"

        root.title("Oolite Key Helper")
        root.geometry(geometry)
        # Not managed by the window manager: no decorations, exact placement,
        # and it never takes focus from the game.
        root.overrideredirect(True)
        root.configure(bg=BG)
        root.bind("<Button-3>", lambda e: root.destroy())  # right-click quits

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=self.px(40), pady=self.px(24, 8))
        self.context_label = tk.Label(header, font=self.font(SANS, 44, "bold"), fg=ACCENT, bg=BG)
        narrow = self.columns == 1  # stack the details under the heading
        self.context_label.pack(side="top" if narrow else "left", anchor="w")
        self.detail_label = tk.Label(
            header, font=self.font(SANS, 20), fg=DIM, bg=BG, justify="left" if narrow else "right"
        )
        if narrow:
            self.detail_label.pack(side="top", anchor="w")
        else:
            self.detail_label.pack(side="right", anchor="s", pady=self.px(0, 10))

        tabs = tk.Frame(root, bg=BG)
        tabs.pack(fill="x", padx=self.px(40), pady=self.px(0, 8))
        self.tab_labels = {}
        for name, title in TABS:
            label = tk.Label(tabs, text=f"  {title}  ", font=self.font(SANS, 16, "bold"), bg=BG)
            label.pack(side="left", padx=self.px(0, 12))
            # Left-click only: clicking never moves keyboard focus off the game (#20).
            label.bind("<Button-1>", lambda e, name=name: self.choose_tab(name))
            self.tab_labels[name] = label
        # Drive status chips on the right of the tab row, while flying.
        self.indicator_labels = {}
        for name in ("JUMP", "TORUS"):
            label = tk.Label(tabs, font=self.font(SANS, 16, "bold"), bg=BG)
            label.pack(side="right", padx=self.px(12, 0))
            self.indicator_labels[name] = label

        self.tip_label = tk.Label(
            root,
            font=self.font(SANS, 20),
            fg=FG,
            bg=BG,
            anchor="w",
            justify="left",
            wraplength=width - self.px(80),
        )
        self.tip_label.pack(fill="x", padx=self.px(40))

        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=self.px(28))
        for c in range(self.columns):
            self.body.columnconfigure(c, weight=1, uniform="col")

        self.status_label = tk.Label(root, font=self.font(MONO, 12), fg=DIM, bg=BG, anchor="w")
        self.status_label.pack(fill="x", padx=self.px(40), pady=self.px(0, 12))

        self.render()
        self.tick()

    def font(self, family, size, *style):
        return (family, max(9, round(size * self.scale)), *style)  # 9: still readable

    def px(self, *sizes):
        """Spacing scaled with the text: one size, or a (before, after) pair."""
        scaled = tuple(round(size * self.scale) for size in sizes)
        return scaled[0] if len(scaled) == 1 else scaled

    def tick(self):
        # Any unexpected error is reported and polling carries on: stopping here
        # would leave the window showing stale information with no sign why.
        try:
            if not self.poll_once():
                return  # the game closed and the window went with it
        except Exception as exc:
            self.report(exc)
            self.status_label.config(text=self.status_text())
        self.root.after(POLL_MS, self.tick)

    def poll_once(self):
        """Read and apply new messages and redraw; False once the window is gone."""
        messages = self.source.poll()
        quit_for_game = should_quit_for_messages(messages, self.first_poll, self.quit_with_game)
        applied = False
        for msg in messages:
            try:
                self.market_store.apply(msg)
                self.state.apply(msg)
            except Exception as exc:  # one bad message mustn't drop the rest
                self.report(exc, msg)
                continue
            applied = True
            self.last_message = json.dumps(msg)
            if msg.get("type") == "closed" and quit_for_game:
                self.root.destroy()
                return False
        if applied:
            self.error = self.notice = None
        self.first_poll = False
        if (
            messages
            or self.state.countdown_left is not None
            or self.market_store.price_age != self.shown_market_age
        ):
            self.render()
        return True

    def report(self, exc, msg=None):
        error = f"{type(exc).__name__}: {exc}"
        if error != self.error:  # once per distinct error, not every tick
            print(
                f"oolite-helper: {error}" + (f" (message: {msg})" if msg else ""), file=sys.stderr
            )
            traceback.print_exc()
        self.error = error

    def status_text(self):
        if self.error:
            return f"Error (still running): {self.error}"
        return self.keymap_error or self.notice or self.last_message

    def render(self):
        context = self.state.context
        self.context_label.config(
            text=context.upper(), fg=RED if context in ("red alert", "ship destroyed") else ACCENT
        )
        screen = (self.state.gui or "-").replace("GUI_SCREEN_", "").replace("_", " ").title()
        view = (self.state.view or "-").replace("VIEW_", "").replace("_", " ").title()
        lines = ["    ".join(self.state.details), f"Screen: {screen}    View: {view}"]
        market_age = self.market_store.price_age
        if market_age:
            lines.append(f"Market prices: {market_age}")
        self.shown_market_age = market_age
        self.detail_label.config(text="\n".join(line for line in lines if line))
        tip_text = tip(self.state, self.keymap)
        self.tip_label.config(text=tip_text, pady=self.px(8) if tip_text else 0)
        self.status_label.config(text=self.status_text())

        tab = self.visible_tab()
        for name, label in self.tab_labels.items():
            active = name == tab
            label.config(fg=BG if active else DIM, bg=ACCENT if active else PANEL)
        shown = {name: (ok, why) for name, ok, why in indicators(self.state)}
        for name, label in self.indicator_labels.items():
            if name not in shown:
                label.config(text="", bg=BG)
                continue
            ok, why = shown[name]
            text = f"  {name} ✓  " if ok else f"  {name} ✗ {why}  "
            label.config(text=text, fg=BG, bg=GREEN if ok else RED)
        if tab == "trade" and self.trade_commodity:
            wanted = self.trade_detail()
        elif tab == "trade":
            rows = commodity_rows(
                self.state, self.market_store.data["markets"], self.market_store.now()
            )
            wanted = ("trade", self.trade_sort, tuple(sort_rows(rows, *self.trade_sort)))
        elif not self.keymap:
            wanted = None
        elif tab == "all":
            wanted = ("all", self.all_group)
        else:
            wanted = sections(self.state)
        if wanted != self.shown:
            for child in self.body.winfo_children():
                child.destroy()
            if wanted and wanted[0] == "trade":
                self.draw_trade(wanted[2])
            elif wanted and wanted[0] == "detail":
                self.draw_detail(*wanted[1:])
            elif wanted and wanted[0] == "all":
                self.draw_all_keys(self.all_group)
            elif wanted:
                self.draw_sections(wanted)
            self.shown = wanted

    def visible_tab(self):
        return "keys" if self.state.context in URGENT else self.tab

    def choose_tab(self, name):
        self.tab = name
        self.render()

    def choose_group(self, index):
        self.all_group = index
        self.render()

    def sort_trade(self, key, high_first):
        column, descending = self.trade_sort
        self.trade_sort = (key, not descending) if column == key else (key, high_first)
        self.render()

    def open_commodity(self, commodity):
        self.trade_commodity = commodity
        self.trade_destination = self.trade_quantity = None
        self.render()

    def choose_destination(self, system_id):
        self.trade_destination = system_id
        self.render()

    def change_quantity(self, quantity):
        self.trade_quantity = quantity
        self.render()

    def trade_detail(self):
        """What the detail view shows for the open commodity, as a comparable tuple."""
        markets, now = self.market_store.data["markets"], self.market_store.now()
        commodity = self.trade_commodity
        row = next(
            (r for r in commodity_rows(self.state, markets, now) if r.commodity == commodity), None
        )
        offers = tuple(commodity_offers(self.state, markets, now, commodity))
        offer = next((o for o in offers if o.system_id == self.trade_destination), None)
        offer = offer or (offers[0] if offers else None)
        limit = buy_limit(self.state, markets, now, commodity)
        quantity = limit.most if self.trade_quantity is None else self.trade_quantity
        quantity = max(0, min(quantity, limit.most))
        keys = self.keymap.keys if self.keymap else (lambda action: "")
        steps = trade_steps(
            keys,
            self.commodity_name(commodity),
            quantity,
            limit.most,
            offer,
            self.state,
            held(self.state, commodity),
        )
        return ("detail", commodity, row, offers, offer, limit, quantity, tuple(steps))

    def commodity_name(self, key):
        return self.keymap.commodity(key) if self.keymap else commodity_fallback(key)

    def draw_trade(self, rows):
        """Each commodity's price here against the best price within fuel range."""
        panel = tk.Frame(self.body, bg=PANEL, padx=self.px(18), pady=self.px(12))
        panel.grid(
            row=0,
            column=0,
            columnspan=self.columns,
            sticky="new",
            padx=self.px(12),
            pady=self.px(12),
        )
        if not rows:
            tk.Label(
                panel,
                text="No market data yet. Dock at a station, or wait for the systems in "
                "fuel range to arrive.",
                font=self.font(SANS, 18),
                fg=DIM,
                bg=PANEL,
            ).grid(row=0, column=0, sticky="w")
            return
        column, descending = self.trade_sort
        for c, (key, title, high_first) in enumerate(TRADE_COLUMNS):
            arrow = (" ▼" if descending else " ▲") if key == column else ""
            header = tk.Label(
                panel,
                text=title + arrow,
                font=self.font(SANS, 16, "bold"),
                fg=ACCENT if key == column else DIM,
                bg=PANEL,
            )
            header.grid(row=0, column=c, sticky="w", padx=self.px(0, 28), pady=self.px(0, 6))
            # Left-click only, like the tabs: focus stays with the game.
            header.bind("<Button-1>", lambda e, k=key, h=high_first: self.sort_trade(k, h))
        for r, row in enumerate(rows, start=1):
            name = self.commodity_name(row.commodity) + ("  illegal" if row.illegal else "")
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
                cell = tk.Label(panel, text=text, font=self.font(family, 18), fg=colour, bg=PANEL)
                cell.grid(row=r, column=c, sticky="w", padx=self.px(0, 28))
                cell.bind("<Button-1>", lambda e, k=row.commodity: self.open_commodity(k))
        tk.Label(
            panel,
            text="Click a commodity for every system in range, a quantity and the keys to press.",
            font=self.font(SANS, 14),
            fg=DIM,
            bg=PANEL,
        ).grid(
            row=len(rows) + 1,
            column=0,
            columnspan=len(TRADE_COLUMNS),
            sticky="w",
            pady=self.px(8, 0),
        )

    def draw_detail(self, commodity, row, offers, offer, limit, quantity, steps):
        """One commodity: every system in range, a quantity picker and the keys to press."""
        panel = tk.Frame(self.body, bg=PANEL, padx=self.px(18), pady=self.px(12))
        panel.grid(
            row=0,
            column=0,
            columnspan=self.columns,
            sticky="new",
            padx=self.px(12),
            pady=self.px(12),
        )
        name = self.commodity_name(commodity)
        unit = row.unit if row else "t"
        top = tk.Frame(panel, bg=PANEL)
        top.pack(fill="x", anchor="w")
        back = tk.Label(
            top, text="◀ All commodities", font=self.font(SANS, 16), fg=ACCENT, bg=PANEL
        )
        back.pack(side="left", padx=self.px(0, 28))
        back.bind("<Button-1>", lambda e: self.open_commodity(None))
        here = ""
        if row and row.here is not None:
            here = f"here {_price(row.here, row.here_note)}, {row.stock or 0} {unit} on sale"
        tk.Label(
            top,
            text=f"{name}{'  illegal here' if row and row.illegal else ''}   {here}",
            font=self.font(SANS, 20, "bold"),
            fg=RED if row and row.illegal else FG,
            bg=PANEL,
        ).pack(side="left")

        table = tk.Frame(panel, bg=PANEL)
        table.pack(fill="x", anchor="w", pady=self.px(10, 0))
        if not offers:
            tk.Label(
                table,
                text="No prices for systems in fuel range yet.",
                font=self.font(SANS, 18),
                fg=DIM,
                bg=PANEL,
            ).grid(row=0, column=0, sticky="w")
        titles = ("Sell at", "Price", "Margin", "Distance", "Economy", "Government")
        for c, title in enumerate(titles if offers else ()):
            tk.Label(table, text=title, font=self.font(SANS, 16, "bold"), fg=DIM, bg=PANEL).grid(
                row=0, column=c, sticky="w", padx=self.px(0, 28), pady=self.px(0, 6)
            )
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
                cell = tk.Label(table, text=text, font=self.font(family, 18), fg=colour, bg=PANEL)
                cell.grid(row=r, column=c, sticky="w", padx=self.px(0, 28))
                cell.bind("<Button-1>", lambda e, i=o.system_id: self.choose_destination(i))

        picker = tk.Frame(panel, bg=PANEL)
        picker.pack(fill="x", anchor="w", pady=self.px(14, 0))
        tk.Label(picker, text="Buy", font=self.font(SANS, 18, "bold"), fg=DIM, bg=PANEL).pack(
            side="left", padx=self.px(0, 14)
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
                font=self.font(MONO if value is None else SANS, 18, "bold"),
                fg=ACCENT if value is None else FG,
                bg=PANEL if value is None else BG,
            )
            button.pack(side="left", padx=self.px(0, 8))
            if value is not None:
                v = max(0, min(value, limit.most))
                button.bind("<Button-1>", lambda e, v=v: self.change_quantity(v))
        tk.Label(
            picker,
            text=f"most {limit.most} ({limit.reason})",
            font=self.font(SANS, 16),
            fg=DIM,
            bg=PANEL,
        ).pack(side="left", padx=self.px(14, 0))

        summary = []
        if row and row.here is not None:
            summary.append(f"Cost {quantity * row.here / 10:.1f} cr")
            summary.append(f"cargo {quantity} {unit}")
            if offer is not None:
                profit = quantity * (offer.price - row.here) / 10
                summary.append(f"profit at {offer.name} {profit:+.1f} cr")
        if summary:
            tk.Label(
                panel, text="    ".join(summary), font=self.font(SANS, 18), fg=FG, bg=PANEL
            ).pack(anchor="w", pady=self.px(8, 0))

        for i, step in enumerate(steps, start=1):
            tk.Label(
                panel,
                text=f"{i}. {step}",
                font=self.font(SANS, 18),
                fg=FG,
                bg=PANEL,
                justify="left",
                wraplength=self.desc_wrap * self.columns,
            ).pack(anchor="w", pady=self.px(8 if i == 1 else 2, 0))

    def draw_sections(self, wanted):
        for i, (title, actions) in enumerate(wanted):
            self.draw_panel(self.body, i // self.columns, i % self.columns, title, actions)

    def draw_all_keys(self, current):
        """The game's key groups as clickable chips, and the chosen group's keys."""
        chips = tk.Frame(self.body, bg=BG)
        chips.grid(
            row=0,
            column=0,
            columnspan=self.columns,
            sticky="w",
            padx=self.px(12),
            pady=self.px(4, 0),
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
                text=f" {self.keymap.describe(header)} ",
                font=self.font(SANS, 14),
                fg=BG if active else FG,
                bg=ACCENT if active else PANEL,
            )
            chip.pack(side="left", padx=self.px(0, 8), pady=self.px(4))
            chip.bind("<Button-1>", lambda e, i=i: self.choose_group(i))
        header, actions = ALL_KEY_GROUPS[current]
        panel = self.draw_panel(
            self.body, 1, 0, self.keymap.describe(header), actions, show_unbound=True
        )
        panel.grid(columnspan=self.columns)

    def draw_panel(self, parent, row, column, title, actions, show_unbound=False):
        panel = tk.Frame(parent, bg=PANEL, padx=self.px(18), pady=self.px(12))
        panel.grid(row=row, column=column, sticky="new", padx=self.px(12), pady=self.px(12))
        if title:
            tk.Label(
                panel,
                text=title.upper(),
                font=self.font(SANS, 16, "bold"),
                fg=DIM,
                bg=PANEL,
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=self.px(0, 6))
        row = 1
        for action in actions:
            keys = self.keymap.keys(action)
            if not keys and not show_unbound:
                continue  # unbound in this setup
            tk.Label(
                panel,
                text=keys or "—",
                font=self.font(MONO, 20, "bold"),
                fg=ACCENT if keys else DIM,
                bg=PANEL,
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=self.px(0, 18))
            text = self.keymap.describe(action)
            if action in ACTION_NOTES:
                text += f" ({ACTION_NOTES[action]})"
            tk.Label(
                panel,
                text=text,
                font=self.font(SANS, 20),
                fg=FG if keys else DIM,
                bg=PANEL,
                anchor="w",
                justify="left",
                wraplength=self.desc_wrap,
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


def single_instance_lock():
    """Hold an exclusive lock for the life of the process; None if another helper has it."""
    path = os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()), "oolite-helper.lock"
    )
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


def main():
    parser = argparse.ArgumentParser(
        description="Context-aware key helper for Oolite.",
        epilog=f"Window settings can also go in {config.PATH} (see README).",
    )
    parser.add_argument("--log", default=DEFAULT_LOG, help="path to Oolite's Latest.log")
    parser.add_argument("--stay", action="store_true", help="keep running when the game exits")
    parser.add_argument(
        "--list-screens", action="store_true", help="list the monitors xrandr reports and exit"
    )
    win = parser.add_argument_group("window placement (overrides the config file)")
    win.add_argument(
        "--screen", help="monitor name from --list-screens (default: first non-primary monitor)"
    )
    win.add_argument("--width", help="pixels or percent of the screen, e.g. 40%%")
    win.add_argument("--height", help="pixels or percent of the screen")
    win.add_argument("--anchor", choices=ANCHORS, help="where on the screen to sit")
    win.add_argument("--margin", type=int, help="pixels from the screen edges")
    win.add_argument(
        "--layout",
        choices=config.LAYOUTS,
        help="compact: smaller text and spacing, more key columns",
    )
    win.add_argument("--font-scale", type=float, help="text size multiplier, e.g. 0.8")
    win.add_argument("--geometry", help="exact X geometry WxH+X+Y; overrides the others")
    args = parser.parse_args()

    monitors = list_monitors()
    if args.list_screens:
        for m in monitors:
            print(m)
        return

    settings = config.load_window_settings(
        overrides={
            "screen": args.screen,
            "width": args.width,
            "height": args.height,
            "anchor": args.anchor,
            "margin": args.margin,
            "layout": args.layout,
            "font_scale": args.font_scale,
            "geometry": args.geometry,
        }
    )
    window_geometry = settings["geometry"]
    if not window_geometry:
        monitor = choose_monitor(monitors, settings["screen"])
        if monitor is None:
            raise SystemExit(
                "No monitors found via xrandr; set geometry in the config "
                "file or use --geometry WxH+X+Y"
            )
        window_geometry = geometry(
            monitor, settings["width"], settings["height"], settings["anchor"], settings["margin"]
        )

    lock = single_instance_lock()
    if lock is None:
        print("oolite-helper is already running", file=sys.stderr)
        return

    root = tk.Tk()
    HelperWindow(
        root,
        LogSource(args.log),
        window_geometry,
        quit_with_game=not args.stay,
        font_scale=float(settings["font_scale"]),
        layout=settings["layout"],
    )
    root.mainloop()
