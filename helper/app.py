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
from .contexts import ACTION_NOTES, ALL_KEY_GROUPS, sections, tip
from .keys import load_keymap
from .markets import MarketStore
from .screen import ANCHORS, choose_monitor, geometry, list_monitors
from .sources import DEFAULT_LOG, LogSource
from .state import GameState

POLL_MS = 200
MAX_COLUMNS = 3
COLUMN_WIDTH = 600  # px a key panel needs at font scale 1.0
BG = "#101418"
PANEL = "#171d23"
FG = "#e6e6e6"
ACCENT = "#ffb000"
RED = "#ff4040"
DIM = "#7a8590"
SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

TABS = (("keys", "Keys"), ("all", "All keys"))
# Contexts that switch the view back to Keys whatever tab is chosen; the chosen
# tab comes back when they end.
URGENT = ("red alert", "jump countdown", "ship destroyed")


def should_quit_for_messages(messages, first_poll, quit_with_game=True):
    """Whether a close message is a live exit rather than old log replay."""
    replay = first_poll or any(m.get("type") == "session" for m in messages)
    return quit_with_game and not replay and any(m.get("type") == "closed" for m in messages)


class HelperWindow:
    def __init__(self, root, source, geometry, quit_with_game=True, font_scale=1.0):
        self.root = root
        self.source = source
        self.quit_with_game = quit_with_game
        self.scale = font_scale
        width = int(geometry.split("x", 1)[0])
        self.columns = max(1, min(MAX_COLUMNS, int(width / (COLUMN_WIDTH * font_scale))))
        self.desc_wrap = int(width / self.columns * 0.6)
        self.first_poll = True
        self.state = GameState()
        self.market_store = MarketStore()
        self.notice = self.market_store.load_error  # shown until the game sends something
        self.shown_market_age = None
        self.shown = None  # what the body currently shows
        self.tab = "keys"  # the tab the player chose
        self.all_group = 0  # group shown on the All keys tab
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
        header.pack(fill="x", padx=40, pady=(24, 8))
        self.context_label = tk.Label(header, font=self.font(SANS, 44, "bold"), fg=ACCENT, bg=BG)
        narrow = self.columns == 1  # stack the details under the heading
        self.context_label.pack(side="top" if narrow else "left", anchor="w")
        self.detail_label = tk.Label(
            header, font=self.font(SANS, 20), fg=DIM, bg=BG, justify="left" if narrow else "right"
        )
        if narrow:
            self.detail_label.pack(side="top", anchor="w")
        else:
            self.detail_label.pack(side="right", anchor="s", pady=(0, 10))

        tabs = tk.Frame(root, bg=BG)
        tabs.pack(fill="x", padx=40, pady=(0, 8))
        self.tab_labels = {}
        for name, title in TABS:
            label = tk.Label(tabs, text=f"  {title}  ", font=self.font(SANS, 16, "bold"), bg=BG)
            label.pack(side="left", padx=(0, 12))
            # Left-click only: clicking never moves keyboard focus off the game (#20).
            label.bind("<Button-1>", lambda e, name=name: self.choose_tab(name))
            self.tab_labels[name] = label

        self.tip_label = tk.Label(
            root,
            font=self.font(SANS, 20),
            fg=FG,
            bg=BG,
            anchor="w",
            justify="left",
            wraplength=width - 80,
        )
        self.tip_label.pack(fill="x", padx=40)

        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=28)
        for c in range(self.columns):
            self.body.columnconfigure(c, weight=1, uniform="col")

        self.status_label = tk.Label(root, font=self.font(MONO, 12), fg=DIM, bg=BG, anchor="w")
        self.status_label.pack(fill="x", padx=40, pady=(0, 12))

        self.render()
        self.tick()

    def font(self, family, size, *style):
        return (family, max(6, round(size * self.scale)), *style)

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
        self.tip_label.config(text=tip_text, pady=8 if tip_text else 0)
        self.status_label.config(text=self.status_text())

        tab = self.visible_tab()
        for name, label in self.tab_labels.items():
            active = name == tab
            label.config(fg=BG if active else DIM, bg=ACCENT if active else PANEL)
        if not self.keymap:
            wanted = None
        elif tab == "all":
            wanted = ("all", self.all_group)
        else:
            wanted = sections(self.state)
        if wanted != self.shown:
            for child in self.body.winfo_children():
                child.destroy()
            if wanted and wanted[0] == "all":
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

    def draw_sections(self, wanted):
        for i, (title, actions) in enumerate(wanted):
            self.draw_panel(self.body, i // self.columns, i % self.columns, title, actions)

    def draw_all_keys(self, current):
        """The game's key groups as clickable chips, and the chosen group's keys."""
        chips = tk.Frame(self.body, bg=BG)
        chips.grid(row=0, column=0, columnspan=self.columns, sticky="w", padx=12, pady=(4, 0))
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
            chip.pack(side="left", padx=(0, 8), pady=4)
            chip.bind("<Button-1>", lambda e, i=i: self.choose_group(i))
        header, actions = ALL_KEY_GROUPS[current]
        panel = self.draw_panel(
            self.body, 1, 0, self.keymap.describe(header), actions, show_unbound=True
        )
        panel.grid(columnspan=self.columns)

    def draw_panel(self, parent, row, column, title, actions, show_unbound=False):
        panel = tk.Frame(parent, bg=PANEL, padx=18, pady=12)
        panel.grid(row=row, column=column, sticky="new", padx=12, pady=12)
        if title:
            tk.Label(
                panel,
                text=title.upper(),
                font=self.font(SANS, 16, "bold"),
                fg=DIM,
                bg=PANEL,
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
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
            ).grid(row=row, column=0, sticky="w", padx=(0, 18))
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
    )
    root.mainloop()
