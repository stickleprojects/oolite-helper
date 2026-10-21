"""The helper window."""

import argparse
import json
import tkinter as tk
from collections import deque

from .sources import DEFAULT_LOG, LogSource
from .state import GameState

POLL_MS = 200
BG = "#101418"
FG = "#e6e6e6"
ACCENT = "#ffb000"
DIM = "#7a8590"


class HelperWindow:
    def __init__(self, root, source, geometry, quit_with_game=True):
        self.root = root
        self.source = source
        self.quit_with_game = quit_with_game
        # The first poll replays the existing log; a "closed" there is an old
        # game ending, not this one.
        self.first_poll = True
        self.state = GameState()
        self.recent = deque(maxlen=12)

        root.title("Oolite Key Helper")
        root.geometry(geometry)
        # Not managed by the window manager: no decorations, exact placement,
        # and it never takes focus from the game.
        root.overrideredirect(True)
        root.configure(bg=BG)
        root.bind("<Button-3>", lambda e: root.destroy())  # right-click quits

        self.context_label = tk.Label(
            root, font=("DejaVu Sans", 48, "bold"), fg=ACCENT, bg=BG, anchor="w")
        self.context_label.pack(fill="x", padx=40, pady=(30, 0))
        self.detail_label = tk.Label(
            root, font=("DejaVu Sans", 24), fg=FG, bg=BG, anchor="w")
        self.detail_label.pack(fill="x", padx=40)
        self.log_label = tk.Label(
            root, font=("DejaVu Sans Mono", 16), fg=DIM, bg=BG,
            anchor="nw", justify="left")
        self.log_label.pack(fill="both", expand=True, padx=40, pady=30)

        self.render()
        self.tick()

    def tick(self):
        messages = self.source.poll()
        for msg in messages:
            if msg.get("type") == "session":
                self.recent.clear()
            self.state.apply(msg)
            self.recent.append(json.dumps(msg))
            if msg.get("type") == "closed" and self.quit_with_game and not self.first_poll:
                self.root.destroy()
                return
        self.first_poll = False
        if messages:
            self.render()
        self.root.after(POLL_MS, self.tick)

    def render(self):
        self.context_label.config(text=self.state.context.replace("_", " ").upper())
        screen = (self.state.gui or "-").replace("GUI_SCREEN_", "").replace("_", " ").title()
        view = (self.state.view or "-").replace("VIEW_", "").replace("_", " ").title()
        self.detail_label.config(text=f"Screen: {screen}    View: {view}")
        self.log_label.config(text="\n".join(reversed(self.recent)))


def main():
    parser = argparse.ArgumentParser(description="Context-aware key helper for Oolite.")
    parser.add_argument("--log", default=DEFAULT_LOG, help="path to Oolite's Latest.log")
    parser.add_argument("--geometry", default="1920x1080+960+1080",
                        help="window size and position (default: the laptop screen)")
    parser.add_argument("--stay", action="store_true",
                        help="keep running when the game exits")
    args = parser.parse_args()

    root = tk.Tk()
    HelperWindow(root, LogSource(args.log), args.geometry, quit_with_game=not args.stay)
    root.mainloop()
