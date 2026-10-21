"""The helper window."""

import argparse
import fcntl
import json
import os
import sys
import tempfile
import tkinter as tk

from .contexts import ACTION_NOTES, sections, tip
from .keys import load_keymap
from .sources import DEFAULT_LOG, LogSource
from .state import GameState

POLL_MS = 200
COLUMNS = 3
BG = "#101418"
PANEL = "#171d23"
FG = "#e6e6e6"
ACCENT = "#ffb000"
RED = "#ff4040"
DIM = "#7a8590"
SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"


class HelperWindow:
    def __init__(self, root, source, geometry, quit_with_game=True):
        self.root = root
        self.source = source
        self.quit_with_game = quit_with_game
        self.first_poll = True
        self.state = GameState()
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
        self.context_label = tk.Label(header, font=(SANS, 44, "bold"), fg=ACCENT, bg=BG)
        self.context_label.pack(side="left")
        self.detail_label = tk.Label(header, font=(SANS, 20), fg=DIM, bg=BG, justify="right")
        self.detail_label.pack(side="right", anchor="s", pady=(0, 10))

        self.tip_label = tk.Label(root, font=(SANS, 20), fg=FG, bg=BG, anchor="w",
                                  justify="left", wraplength=1800)
        self.tip_label.pack(fill="x", padx=40)

        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=28)
        for c in range(COLUMNS):
            self.body.columnconfigure(c, weight=1, uniform="col")

        self.status_label = tk.Label(root, font=(MONO, 12), fg=DIM, bg=BG, anchor="w")
        self.status_label.pack(fill="x", padx=40, pady=(0, 12))

        self.render()
        self.tick()

    def tick(self):
        messages = self.source.poll()
        # A "closed" read along with the file it came in (first read of a newly
        # opened log) is an old game's ending, not a live exit.
        replay = self.first_poll or any(m.get("type") == "session" for m in messages)
        for msg in messages:
            self.state.apply(msg)
            self.last_message = json.dumps(msg)
            if msg.get("type") == "closed" and self.quit_with_game and not replay:
                self.root.destroy()
                return
        self.first_poll = False
        if messages or self.state.countdown_left is not None:  # countdown ticks live
            self.render()
        self.root.after(POLL_MS, self.tick)

    def render(self):
        context = self.state.context
        self.context_label.config(text=context.upper(),
                                  fg=RED if context == "red alert" else ACCENT)
        screen = (self.state.gui or "-").replace("GUI_SCREEN_", "").replace("_", " ").title()
        view = (self.state.view or "-").replace("VIEW_", "").replace("_", " ").title()
        lines = ["    ".join(self.state.details), f"Screen: {screen}    View: {view}"]
        self.detail_label.config(text="\n".join(l for l in lines if l))
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
            panel.grid(row=i // COLUMNS, column=i % COLUMNS, sticky="new", padx=12, pady=12)
            tk.Label(panel, text=title.upper(), font=(SANS, 16, "bold"), fg=DIM,
                     bg=PANEL, anchor="w").grid(row=0, column=0, columnspan=2, sticky="w",
                                                pady=(0, 6))
            row = 1
            for action in actions:
                keys = self.keymap.keys(action)
                if not keys:
                    continue  # unbound in this setup
                tk.Label(panel, text=keys, font=(MONO, 20, "bold"), fg=ACCENT, bg=PANEL,
                         anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 18))
                text = self.keymap.describe(action)
                if action in ACTION_NOTES:
                    text += f" ({ACTION_NOTES[action]})"
                tk.Label(panel, text=text, font=(SANS, 20), fg=FG, bg=PANEL, anchor="w",
                         justify="left", wraplength=440).grid(row=row, column=1, sticky="w")
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
    parser = argparse.ArgumentParser(description="Context-aware key helper for Oolite.")
    parser.add_argument("--log", default=DEFAULT_LOG, help="path to Oolite's Latest.log")
    parser.add_argument("--geometry", default="1920x1080+960+1080",
                        help="window size and position (default: the laptop screen)")
    parser.add_argument("--stay", action="store_true",
                        help="keep running when the game exits")
    args = parser.parse_args()

    lock = single_instance_lock()
    if lock is None:
        print("oolite-helper is already running", file=sys.stderr)
        return

    root = tk.Tk()
    HelperWindow(root, LogSource(args.log), args.geometry, quit_with_game=not args.stay)
    root.mainloop()
