"""Widgets: views in their own small windows, placed anywhere or docked to the game (#50).

Configured in config.toml as an array of [[widgets]] tables:

    [[widgets]]
    views = ["clearance", "drive"]   # one or more of VIEWS, side by side
    dock = "game:top"                # game:top / game:bottom / game:left / game:right

    [[widgets]]
    views = ["trade_here"]
    dock = "game:right"
    width = 520

    [[widgets]]                      # or free, on a monitor
    views = ["drive"]
    screen = "eDP-1"
    x = 0
    y = 0

Docked widgets sit outside the game window (above its title bar, below it, or
beside it), follow it when it moves, and show only while it's the active
window: the #50 spike found topmost widgets would otherwise cover other apps.
The helper only reads the game window's position; it never moves the game.
"""

import os
import tkinter as tk
import tomllib
from dataclasses import dataclass

from . import config
from .views.chips import ClearanceBadge, DriveChips
from .views.style import BG, LAYOUTS, Style
from .views.trade_here import TradeHere

# View name -> factory(model, style, parent frame). Each packs itself into the frame.
VIEWS = {
    "drive": DriveChips,  # TORUS ✓/✗ and JUMP ✓/✗
    "clearance": ClearanceBadge,  # docking clearance near a station
    "trade_here": TradeHere,  # hold, last market, best buys (while docked)
}
DOCKS = ("game:top", "game:bottom", "game:left", "game:right")
SHOW = ("with_game", "always")


@dataclass(frozen=True)
class WidgetSpec:
    views: tuple
    dock: str | None = None  # one of DOCKS, or None for a free widget
    screen: str | None = None  # free widgets: monitor name; None = the whole desktop
    x: int = 0  # free: position on that monitor; docked: offset from the docked spot
    y: int = 0
    width: int | None = None  # None: the game's width (top/bottom) or what the views need
    height: int | None = None  # None: the game's height (left/right) or what the views need
    layout: str = "compact"
    font_scale: float = 1.0
    show: str | None = None  # SHOW; default with_game when docked, always when free

    @property
    def shown(self):
        return self.show or ("with_game" if self.dock else "always")


def load_widgets(path=config.PATH):
    """The [[widgets]] from the config file; [] if none. Bad entries stop with a message."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        entries = tomllib.load(f).get("widgets", [])
    if not isinstance(entries, list):
        raise SystemExit(f"{path}: widgets must be an array of [[widgets]] tables")
    return [_spec(path, n, entry) for n, entry in enumerate(entries, start=1)]


def _spec(path, n, entry):
    where = f"{path}: widget {n}"
    if not isinstance(entry, dict):
        raise SystemExit(f"{where} must be a table")
    known = set(WidgetSpec.__dataclass_fields__)
    unknown = set(entry) - known
    if unknown:
        raise SystemExit(f"{where}: unknown settings: {', '.join(sorted(unknown))}")
    views = entry.get("views")
    if isinstance(views, str):
        views = [views]
    if not views or not all(view in VIEWS for view in views):
        raise SystemExit(f"{where}: views must be one or more of {', '.join(VIEWS)}")
    checks = (
        ("dock", entry.get("dock") in (None, *DOCKS), f"one of {', '.join(DOCKS)}"),
        ("layout", entry.get("layout", "compact") in LAYOUTS, f"one of {', '.join(LAYOUTS)}"),
        ("show", entry.get("show") in (None, *SHOW), f"one of {', '.join(SHOW)}"),
    )
    for name, ok, wanted in checks:
        if not ok:
            raise SystemExit(f"{where}: {name} must be {wanted}")
    for name in ("x", "y", "width", "height"):
        value = entry.get(name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise SystemExit(f"{where}: {name} must be a whole number of pixels")
    scale = entry.get("font_scale", 1.0)
    if not isinstance(scale, (int, float)) or isinstance(scale, bool) or scale <= 0:
        raise SystemExit(f"{where}: font_scale must be a positive number")
    return WidgetSpec(**{**entry, "views": tuple(views), "font_scale": float(scale)})


def place(spec, game_window, size, monitors=()):
    """(x, y, width, height) for a widget, or None when it should be hidden.

    game_window is the model's (geometry, frame, active); size is what the
    views ask for, (width, height).
    """
    geometry, frame, active = game_window
    if spec.shown == "with_game" and not (geometry and active):
        return None
    want_w, want_h = size
    if spec.dock is None:
        origin = next(((m.x, m.y) for m in monitors if m.name == spec.screen), (0, 0))
        return (origin[0] + spec.x, origin[1] + spec.y, spec.width or want_w, spec.height or want_h)
    if geometry is None:
        return None
    gx, gy, gw, gh = geometry
    left, right, top, bottom = frame
    side = spec.dock.split(":")[1]
    if side in ("top", "bottom"):
        w, h = spec.width or gw, spec.height or want_h
        y = gy - top - h if side == "top" else gy + gh + bottom
        return (gx + spec.x, y + spec.y, w, h)
    w, h = spec.width or want_w, spec.height or gh
    x = gx - left - w if side == "left" else gx + gw + right
    return (x + spec.x, gy + spec.y, w, h)


class Widget:
    """One widget window: its views, kept in place by watching the game window."""

    def __init__(self, root, model, spec, monitors=()):
        self.spec = spec
        self.monitors = monitors
        self.window = tk.Toplevel(root, bg=BG)
        # Like the main window: not managed by the window manager, never takes
        # focus from the game (verified for widgets in the #50 spike), on top.
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.withdraw()
        width = spec.width or 600
        style = Style(width, spec.layout, spec.font_scale)
        frame = tk.Frame(self.window, bg=BG, padx=style.px(6), pady=style.px(4))
        frame.pack(fill="both", expand=True)
        self.views = [VIEWS[name](model, style, frame) for name in spec.views]
        self.placed = None
        # Re-place when the game window moves or the views need a different size
        # (Trade here grows when you dock). Tk works sizes out when idle, so a
        # change made in one pass is seen on the next.
        # Views are drawn before this watcher runs (they subscribed first), so
        # their "empty" flags are current.
        self.subscription = model.watch(
            lambda m: (m.topic("game_window"), self.requested_size(), self.empty()), self.follow
        )

    def empty(self):
        return all(view.empty for view in self.views)

    def requested_size(self):
        return (self.window.winfo_reqwidth(), self.window.winfo_reqheight())

    def follow(self, value):
        game_window, size, empty = value
        placed = None if empty else place(self.spec, game_window, size, self.monitors)
        if placed == self.placed:
            return
        self.placed = placed
        if placed is None:
            self.window.withdraw()
            return
        x, y, w, h = placed
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.deiconify()
        self.window.lift()

    def close(self):
        self.subscription.cancel()
        for view in self.views:
            view.close()
        self.window.destroy()
