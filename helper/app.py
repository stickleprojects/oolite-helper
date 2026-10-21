"""The helper window."""

import argparse
import fcntl
import json
import os
import sys
import tempfile
import tkinter as tk

from . import config
from .contexts import ACTION_NOTES, sections, tip
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


def should_quit_for_messages(messages, first_poll, quit_with_game=True):
    """Whether a close message is a live exit rather than old log replay."""
    replay = first_poll or any(m.get("type") == "session" for m in messages)
    return quit_with_game and not replay and any(
        m.get("type") == "closed" for m in messages
    )


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
        self.shown_market_age = None
        self.shown = None  # sections currently drawn
        self.last_message = ""

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
        self.detail_label = tk.Label(header, font=self.font(SANS, 20), fg=DIM, bg=BG,
                                     justify="left" if narrow else "right")
        if narrow:
            self.detail_label.pack(side="top", anchor="w")
        else:
            self.detail_label.pack(side="right", anchor="s", pady=(0, 10))

        self.tip_label = tk.Label(root, font=self.font(SANS, 20), fg=FG, bg=BG, anchor="w",
                                  justify="left", wraplength=width - 80)
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
        messages = self.source.poll()
        quit_for_game = should_quit_for_messages(
            messages, self.first_poll, self.quit_with_game
        )
        for msg in messages:
            self.market_store.apply(msg)
            self.state.apply(msg)
            self.last_message = json.dumps(msg)
            if msg.get("type") == "closed" and quit_for_game:
                self.root.destroy()
                return
        self.first_poll = False
        if messages or self.state.countdown_left is not None \
                or self.market_store.price_age != self.shown_market_age:
            self.render()
        self.root.after(POLL_MS, self.tick)

    def render(self):
        context = self.state.context
        self.context_label.config(text=context.upper(),
                                  fg=RED if context == "red alert" else ACCENT)
        screen = (self.state.gui or "-").replace("GUI_SCREEN_", "").replace("_", " ").title()
        view = (self.state.view or "-").replace("VIEW_", "").replace("_", " ").title()
        lines = ["    ".join(self.state.details), f"Screen: {screen}    View: {view}"]
        market_age = self.market_store.price_age
        if market_age:
            lines.append(f"Market prices: {market_age}")
        self.shown_market_age = market_age
        self.detail_label.config(text="\n".join(line for line in lines if line))
        tip_text = tip(self.state, self.keymap) if self.keymap else ""
        self.tip_label.config(text=tip_text, pady=8 if tip_text else 0)
        self.status_label.config(text=self.keymap_error or self.last_message)

        wanted = sections(self.state) if self.keymap else []
        if wanted != self.shown:
            self.draw_sections(wanted)
            self.shown = wanted

    def draw_sections(self, wanted):
        for child in self.body.winfo_children():
            child.destroy()
        for i, (title, actions) in enumerate(wanted):
            panel = tk.Frame(self.body, bg=PANEL, padx=18, pady=12)
            panel.grid(row=i // self.columns, column=i % self.columns, sticky="new",
                       padx=12, pady=12)
            tk.Label(panel, text=title.upper(), font=self.font(SANS, 16, "bold"), fg=DIM,
                     bg=PANEL, anchor="w").grid(row=0, column=0, columnspan=2, sticky="w",
                                                pady=(0, 6))
            row = 1
            for action in actions:
                keys = self.keymap.keys(action)
                if not keys:
                    continue  # unbound in this setup
                tk.Label(panel, text=keys, font=self.font(MONO, 20, "bold"), fg=ACCENT, bg=PANEL,
                         anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 18))
                text = self.keymap.describe(action)
                if action in ACTION_NOTES:
                    text += f" ({ACTION_NOTES[action]})"
                tk.Label(panel, text=text, font=self.font(SANS, 20), fg=FG, bg=PANEL,
                         anchor="w", justify="left", wraplength=self.desc_wrap
                         ).grid(row=row, column=1, sticky="w")
                row += 1


def single_instance_lock():
    """Hold an exclusive lock for the life of the process; None if another helper has it."""
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()),
                        "oolite-helper.lock")
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
        epilog=f"Window settings can also go in {config.PATH} (see README).")
    parser.add_argument("--log", default=DEFAULT_LOG, help="path to Oolite's Latest.log")
    parser.add_argument("--stay", action="store_true",
                        help="keep running when the game exits")
    parser.add_argument("--list-screens", action="store_true",
                        help="list the monitors xrandr reports and exit")
    win = parser.add_argument_group("window placement (overrides the config file)")
    win.add_argument("--screen", help="monitor name from --list-screens "
                                      "(default: first non-primary monitor)")
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

    settings = config.load_window_settings(overrides={
        "screen": args.screen, "width": args.width, "height": args.height,
        "anchor": args.anchor, "margin": args.margin, "font_scale": args.font_scale,
        "geometry": args.geometry,
    })
    window_geometry = settings["geometry"]
    if not window_geometry:
        monitor = choose_monitor(monitors, settings["screen"])
        if monitor is None:
            raise SystemExit("No monitors found via xrandr; set geometry in the config "
                             "file or use --geometry WxH+X+Y")
        window_geometry = geometry(monitor, settings["width"], settings["height"],
                                   settings["anchor"], settings["margin"])

    lock = single_instance_lock()
    if lock is None:
        print("oolite-helper is already running", file=sys.stderr)
        return

    root = tk.Tk()
    HelperWindow(root, LogSource(args.log), window_geometry,
                 quit_with_game=not args.stay, font_scale=float(settings["font_scale"]))
    root.mainloop()
