"""Where the game window is, and whether it's the active window (#50).

Read-only: the helper never moves or resizes the game. Uses xdotool, xwininfo
and xprop (already needed elsewhere on this X11 setup) with fixed argument
lists. The #50 spike measured polling twice a second as cheap.
"""

import re
import subprocess

GAME_CLASS = "oolite"


def _run(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_geometry(xwininfo):
    """(x, y, width, height) of the client area from xwininfo output, or None."""
    fields = {}
    for key, name in (
        ("Absolute upper-left X", "x"),
        ("Absolute upper-left Y", "y"),
        ("Width", "w"),
        ("Height", "h"),
        ("Map State", "map"),
    ):
        match = re.search(rf"^\s*{key}:\s*(\S+)", xwininfo, re.MULTILINE)
        if match:
            fields[name] = match.group(1)
    if fields.get("map") != "IsViewable" or not {"x", "y", "w", "h"} <= set(fields):
        return None  # minimised, closed or unreadable
    try:
        return tuple(int(fields[name]) for name in ("x", "y", "w", "h"))
    except ValueError:
        return None


def parse_frame_extents(xprop):
    """(left, right, top, bottom) window-manager borders from xprop, or zeros."""
    match = re.search(r"=\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)", xprop)
    return tuple(int(v) for v in match.groups()) if match else (0, 0, 0, 0)


def parse_window_id(text):
    """A window id from xdotool (decimal) or xprop ("window id # 0x3800004")."""
    match = re.search(r"0x[0-9a-fA-F]+|\d+", text.split("#")[-1] if "#" in text else text)
    if not match:
        return None
    return int(match.group(0), 16 if match.group(0).startswith("0x") else 10)


class GameWindow:
    """Polls the game window. poll() returns a "window/game" action for the model."""

    def __init__(self, run=_run):
        self.run = run
        self.window_id = None

    def poll(self):
        if self.window_id is None:
            found = self.run("xdotool", "search", "--class", GAME_CLASS).split()
            self.window_id = int(found[0]) if found else None
        geometry = None
        if self.window_id is not None:
            geometry = parse_geometry(self.run("xwininfo", "-id", str(self.window_id)))
            if geometry is None:
                self.window_id = None  # gone or minimised: look again next time
        frame = (0, 0, 0, 0)
        active = False
        if geometry is not None:
            frame = parse_frame_extents(
                self.run("xprop", "-id", str(self.window_id), "_NET_FRAME_EXTENTS")
            )
            active = (
                parse_window_id(self.run("xprop", "-root", "_NET_ACTIVE_WINDOW")) == self.window_id
            )
        return {"type": "window/game", "geometry": geometry, "frame": frame, "active": active}
