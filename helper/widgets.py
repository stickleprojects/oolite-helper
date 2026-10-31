"""Widgets: windows hosting one or more components, docked to the game or free (#50).

Terms: a component renders part of the model; a widget hosts one or more
components; a widgetwindow (#124) holds one or more widgets under its own title;
a dock is a place beside the game window or a monitor's edge; the layout
(layout.py) places every widget, in a dock or free on a monitor.

Their settings (config.toml's [[widgets]] and [[widgetwindows]], and named
widgets' widget.toml) are read and checked in settings.py, with examples. This
module places them: window_rect and stacked for widgetwindows, place for a
widget on its own, and what edit mode's drags and ⚓ list do (resized,
dropped, move_to).

Docked widgets sit outside the game window (above its title bar, below it, or
beside it), follow it when it moves, and show only while it's the active
window: the #50 spike found topmost widgets would otherwise cover other apps.
The helper only reads the game window's position; it never moves the game.

Widgets are web views by default: plugins.WebWidgets shows the
components as a page built from helper/web. TkWidget below is the fallback,
for ui = "tk" or when the web host can't start; it shows the components that
have a Tk version (TK_COMPONENTS) and leaves the others out.
"""

import tkinter as tk

from .layout import find
from .settings import SCREEN_DOCK
from .tk.components.chips import ClearanceBadge, DriveChips
from .tk.components.style import BG, LAYOUTS, Style
from .tk.components.trade_here import TradeHere

# The ones with a Tk version, for the fallback: name -> factory(model, style,
# parent frame). Each packs itself into the frame.
TK_COMPONENTS = {
    "drive": DriveChips,  # TORUS ✓/✗ and JUMP ✓/✗
    "clearance": ClearanceBadge,  # docking clearance near a station
    "trade_here": TradeHere,  # hold, last market, best buys (while docked)
}


def title_height(window):
    """The px height of a widgetwindow's title bar, for its layout and font_scale."""
    return round(40 * LAYOUTS[window.layout][0] * window.font_scale)


def _length(value, total):
    """A width or height in px: whole pixels as they are, "N%" of total."""
    if isinstance(value, str):
        return round(total * float(value[:-1]) / 100)
    return value


def window_rect(window, game_window, monitors=()):
    """(x, y, width, height) of a widgetwindow, or None to hide it.

    Beside the game it's the game window's whole height, its title bar and
    borders included; above or below, its whole width. On a monitor's edge it's
    that monitor's height or width; floating, its own size on the monitor.
    """
    geometry, frame, active = game_window
    if window.shown == "with_game" and not (geometry and active):
        return None
    if window.on_game:
        if geometry is None:
            return None
        gx, gy, gw, gh = geometry
        left, right, top, bottom = frame
        side = window.dock.split(":")[1]
        if side in ("left", "right"):
            x = gx - left - window.width if side == "left" else gx + gw + right
            return (x, gy - top, window.width, top + gh + bottom)
        y = gy - top - window.height if side == "top" else gy + gh + bottom
        return (gx - left, y, left + gw + right, window.height)
    edge = SCREEN_DOCK.fullmatch(window.dock) if window.dock else None
    name = edge["monitor"] if edge else window.screen
    m = next((m for m in monitors if m.name == name), None)
    if m is None:
        return None
    if edge is None:
        w, h = _length(window.width, m.width), _length(window.height, m.height)
        return (m.x + window.x, m.y + window.y, w, h)
    side = edge["edge"]
    if side in ("left", "right"):
        w = _length(window.width, m.width)
        return (m.x if side == "left" else m.x + m.width - w, m.y, w, m.height)
    h = _length(window.height, m.height)
    return (m.x, m.y if side == "top" else m.y + m.height - h, m.width, h)


def stacked(rect, title, heights):
    """Where a widgetwindow's widgets go, top to bottom under its title bar.

    rect is the widgetwindow's; heights is [(id, height or None if hidden,
    fills)] in order. The widget that fills (else the last shown one) takes
    what the others leave. Returns {id: (x, y, width, height) or None}.
    """
    x, y, w, h = rect
    shown = [(wid, height, fills) for wid, height, fills in heights if height is not None]
    filler = next((wid for wid, _, fills in shown if fills), shown[-1][0] if shown else None)
    left = h - title - sum(height for wid, height, _ in shown if wid != filler)
    rects, top = {}, y + title
    for wid, height, _ in heights:
        if height is None:
            rects[wid] = None
            continue
        height = max(0, left) if wid == filler else height
        rects[wid] = (x, top, w, height)
        top += height
    return rects


def place(spec, game_window, size, monitors=()):
    """(x, y, width, height) for a widget, or None when it should be hidden.

    game_window is the model's (geometry, frame, active); size is what the
    components ask for, (width, height). Not for widgets in a widgetwindow
    (stacked() places those).
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


MIN_SIZE = 80  # px: a widgetwindow can't be resized smaller


def resize_edges(window):
    """The edges of a widgetwindow that resize it in edit mode: the one away from
    where it's docked (beside the game: the far side; on a monitor's edge: the
    inner side), or all four when it floats."""
    if window.dock is None:
        return ("left", "right", "top", "bottom")
    side = window.dock.rsplit(":", 1)[1]
    if window.on_game:
        return (side,)
    return ({"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[side],)


def resized(window, rect, monitors=()):
    """The layout actions that make a widgetwindow the size (and, floating, the
    place) of rect, (x, y, w, h), after an edge was dragged."""
    x, y, w, h = rect
    w, h = max(MIN_SIZE, w), max(MIN_SIZE, h)
    wid = window.id
    if window.dock is None:
        m = next((m for m in monitors if m.name == window.screen), None)
        if m is None:
            return []
        return [
            {"type": "layout/move_widget", "id": wid, "x": x - m.x, "y": y - m.y},
            {"type": "layout/resize_widget", "id": wid, "width": w, "height": h},
        ]
    if window.dock.endswith((":left", ":right")):
        return [{"type": "layout/resize_widget", "id": wid, "width": w}]
    return [{"type": "layout/resize_widget", "id": wid, "height": h}]


ZONE = 48  # px: a widgetwindow dropped with the pointer this close to an edge docks to it


def _game_outer(game_window):
    """The game window with its title bar and borders, (x, y, w, h), or None."""
    geometry, frame, _ = game_window
    if geometry is None:
        return None
    gx, gy, gw, gh = geometry
    left, right, top, bottom = frame
    return (gx - left, gy - top, gw + left + right, gh + top + bottom)


def _monitor_at(monitors, x, y):
    return next(
        (m for m in monitors if m.x <= x < m.x + m.width and m.y <= y < m.y + m.height), None
    )


def places(monitors, game_window):
    """[(place, label)] a widgetwindow can be sent to from its ⚓ list: the game's
    edges (while there's a game window), each monitor's edges, and floating."""
    sides = ("left", "right", "top", "bottom")
    found = []
    if game_window[0] is not None:
        found += [(f"game:{side}", f"Game: {side}") for side in sides]
    for m in monitors:
        found += [(f"screen:{m.name}:{side}", f"{m.name}: {side}") for side in sides]
    return found + [("float", "Float")]


def move_to(window, place, rect, game_window, monitors=(), monitor=None):
    """The layout/move_widget action that sends a widgetwindow, now at rect
    (x, y, w, h), to place: "game:<side>", "screen:<monitor>:<side>" or "float"
    (at rect, on monitor, else the one holding its centre). Docked it keeps its
    width (left, right) or height (top, bottom), but turning from one to the
    other it takes a third of the edge. Coming off a dock to float, the length
    it had along the edge becomes half the monitor's. None if there's nowhere
    to put it."""
    x, y, w, h = rect
    move = {"type": "layout/move_widget", "id": window.id, "x": 0, "y": 0, "screen": None}
    was = (window.dock or "").rsplit(":", 1)[-1]
    if place == "float":
        m = monitor or _monitor_at(monitors, x + w // 2, y + h // 2)
        if m is None:
            return None
        if was in ("left", "right"):
            h = min(h, m.height // 2)
        elif was in ("top", "bottom"):
            w = min(w, m.width // 2)
        x = min(max(x, m.x), m.x + m.width - min(w, m.width))
        y = min(max(y, m.y), m.y + m.height - min(h, m.height))
        return {
            **move,
            "dock": None,
            "screen": m.name,
            "x": x - m.x,
            "y": y - m.y,
            "width": w,
            "height": h,
        }
    side = place.rsplit(":", 1)[1]
    if place.startswith("game:"):
        target = _game_outer(game_window)
    else:
        name = place.split(":")[1]
        m = next((m for m in monitors if m.name == name), None)
        target = (m.x, m.y, m.width, m.height) if m else None
    if target is None:
        return None
    if side in ("left", "right"):
        width = w if was in ("left", "right") else min(w, max(MIN_SIZE, target[2] // 3))
        return {**move, "dock": place, "width": width, "height": None}
    height = h if was in ("top", "bottom") else min(h, max(MIN_SIZE, target[3] // 3))
    return {**move, "dock": place, "width": None, "height": height}


def drop_place(rect, pointer, game_window, monitors=()):
    """Where a widgetwindow dropped with the pointer at pointer (x, y) goes: a game
    edge with the pointer within ZONE px outside it, else a monitor's edge with
    the pointer within ZONE px of it, else "float"."""
    px, py = pointer
    outer = _game_outer(game_window)
    if outer is not None:
        ox, oy, ow, oh = outer
        beside, over = oy <= py <= oy + oh, ox <= px <= ox + ow
        zones = (
            ("right", beside and 0 <= px - (ox + ow) <= ZONE),
            ("left", beside and 0 <= ox - px <= ZONE),
            ("top", over and 0 <= oy - py <= ZONE),
            ("bottom", over and 0 <= py - (oy + oh) <= ZONE),
        )
        side = next((side for side, near in zones if near), None)
        if side:
            return f"game:{side}"
    m = _monitor_at(monitors, px, py)
    if m is not None:
        gaps = {
            "left": px - m.x,
            "right": m.x + m.width - 1 - px,
            "top": py - m.y,
            "bottom": m.y + m.height - 1 - py,
        }
        side = min(gaps, key=gaps.get)
        if gaps[side] <= ZONE:
            return f"screen:{m.name}:{side}"
    return "float"


def dropped(window, rect, game_window, monitors=(), pointer=None):
    """The layout/move_widget action for a widgetwindow dropped at rect after its
    title bar was dragged, the pointer at pointer (default: rect's centre);
    floating, it goes on the monitor holding the pointer."""
    x, y, w, h = rect
    pointer = pointer or (x + w // 2, y + h // 2)
    place = drop_place(rect, pointer, game_window, monitors)
    return move_to(window, place, rect, game_window, monitors, _monitor_at(monitors, *pointer))


def landing(window, rect, game_window, monitors=(), pointer=None):
    """Where a widgetwindow dragged to rect would be once dropped: (x, y, w, h)
    for its ghost, or None."""
    move = dropped(window, rect, game_window, monitors, pointer)
    if move is None:
        return None
    placed = {name: move[name] for name in ("dock", "screen", "x", "y", "width", "height")}
    return window_rect(window.changed(**placed, show="always"), game_window, monitors)


def place_in_window(widgets, window, wid, game_window, height, monitors=(), title=None):
    """A widget's rect in its widgetwindow, or None. height(widget) is a widget's
    height, or None when it isn't shown, so the ones after it move up. title:
    the title bar's height (default title_height(window))."""
    rect = window_rect(window, game_window, monitors)
    if rect is None:
        return None
    inside = [w for w in widgets if w.spec.window == window.id]
    heights = [(w.id, height(w), w.spec.fill) for w in inside]
    title = title_height(window) if title is None else title
    return stacked(rect, title, heights)[wid]


def _configured_height(widget):
    """The Tk fallback has no title bars and stacks by the heights set in
    config.toml: an open widget's (0 if none), or None if it's closed."""
    return (widget.spec.height or 0) if widget.open else None


class TkWidget:
    """One widget as a Tk window (the fallback): its components, kept in place by
    watching the game window and the widget in the model's layout (moved,
    resized, closed)."""

    def __init__(self, root, model, wid, monitors=()):
        self.wid = wid
        spec = find(model.topic("layout"), wid).spec
        self.monitors = monitors
        self.framed = spec.window is not None  # in a widgetwindow (#124)
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
        self.components = [
            TK_COMPONENTS[name](model, style, frame)
            for name in spec.components
            if name in TK_COMPONENTS
        ]
        self.placed = None
        # Re-place when the game window moves or the components need a different size
        # (Trade here grows when you dock). Tk works sizes out when idle, so a
        # change made in one pass is seen on the next.
        # Components are drawn before this watcher runs (they subscribed first), so
        # their "empty" flags are current.
        self.subscription = model.watch(
            lambda m: (
                m.topic("game_window"),
                self.requested_size(),
                self.empty(),
                find(m.topic("layout"), wid),
                self.in_window(m),
            ),
            self.follow,
        )

    def empty(self):
        return all(component.empty for component in self.components)

    def requested_size(self):
        return (self.window.winfo_reqwidth(), self.window.winfo_reqheight())

    def in_window(self, model):
        """Its rect in its widgetwindow (no title bar in Tk), or None."""
        if not self.framed:
            return None
        layout, game_window = model.topic("layout"), model.topic("game_window")
        frame = find(model.topic("windows"), find(layout, self.wid).spec.window)
        if frame is None or not frame.open:
            return None
        return place_in_window(
            layout, frame.spec, self.wid, game_window, _configured_height, self.monitors, 0
        )

    def follow(self, value):
        game_window, size, empty, widget, in_window = value
        hidden = widget is None or not widget.open or (empty and widget.spec.hide_empty)
        if hidden:
            placed = None
        elif self.framed:
            placed = in_window
        else:
            placed = place(widget.spec, game_window, size, self.monitors)
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
        for component in self.components:
            component.close()
        self.window.destroy()
