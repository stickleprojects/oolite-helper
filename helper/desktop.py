"""The desktop's title bar colours, so widgets' title bars match it (#122).

Reads the window manager's theme (Marco on MATE, Metacity's theme format):
the colour it fills a focused window's title bar with, and its title text.
Only plain #rrggbb colours are taken; a theme that draws with GTK colours,
blends or images gives None, and the helper keeps its own colours. Other
window managers (Mutter, KWin, xfwm4) don't use these themes, so they give
None too; the helper only runs on X11 anyway.
"""

import functools
import os
import subprocess
import xml.etree.ElementTree as ET

THEME_KEYS = (
    ("org.mate.Marco.general", "theme"),
    ("org.gnome.desktop.wm.preferences", "theme"),
)
THEME_FILES = ("metacity-theme-3.xml", "metacity-theme-2.xml", "metacity-theme-1.xml")


def _theme_name():
    for schema, key in THEME_KEYS:
        try:
            out = subprocess.run(
                ("gsettings", "get", schema, key), capture_output=True, text=True, timeout=2
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        name = out.strip("'\"")
        if name:
            return name
    return None


def _theme_file(name):
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    home = os.path.expanduser("~/.themes")
    for folder in (home, os.path.join(data_home, "themes"), "/usr/share/themes"):
        for file in THEME_FILES:
            path = os.path.join(folder, name, "metacity-1", file)
            if os.path.isfile(path):
                return path
    return None


def _colour(value):
    value = (value or "").strip()
    if len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
        except ValueError:
            return None
        return value.lower()
    return None


def _lightness(colour):
    r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def readable(text, background):
    """text, or black or white if it's too close to background to read."""
    if text and abs(_lightness(text) - _lightness(background)) > 0.4:
        return text
    return "#000000" if _lightness(background) > 0.5 else "#ffffff"


def _ops_colour(ops, tags):
    """The first plain colour of the first tag in tags that ops draws."""
    for op in ops:
        if op.tag not in tags:
            continue
        if op.tag == "gradient":
            first = op.find("color")
            return None if first is None else _colour(first.get("value"))
        if op.tag == "title" or op.get("filled") == "true":
            return _colour(op.get("color"))
    return None


def title_colours_from(xml):
    """(background, text) of a focused title bar in a Metacity theme, or None."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    ops = {o.get("name"): o for o in root.iter("draw_ops")}
    styles = {s.get("name"): s for s in root.iter("frame_style")}
    sets = {s.get("name"): s for s in root.iter("frame_style_set")}
    window = next((w for w in root.iter("window") if w.get("type") == "normal"), None)
    style_set = sets.get(window.get("style_set")) if window is not None else None
    frame = None
    if style_set is not None:
        frames = style_set.iter("frame")
        wanted = ("yes", "normal")  # focused, not maximised or shaded
        frame = next((f for f in frames if (f.get("focus"), f.get("state")) == wanted), None)
    style = styles.get(frame.get("style")) if frame is not None else None

    def piece_ops(position):
        seen, current = set(), style
        while current is not None and current.get("name") not in seen:
            seen.add(current.get("name"))
            for piece in current.iter("piece"):
                if piece.get("position") == position:
                    named = piece.get("draw_ops")
                    return ops.get(named) if named else piece.find("draw_ops")
            current = styles.get(current.get("parent"))
        return None

    background = None
    for position in ("titlebar", "entire_background"):
        found = piece_ops(position)
        if found is not None:
            background = _ops_colour(found, ("rectangle", "gradient"))
            if background:
                break
    title = piece_ops("title")
    text = _ops_colour(title, ("title",)) if title is not None else None
    return (background, readable(text, background)) if background else None


@functools.cache
def title_colours():
    """(background, text) of the desktop's focused title bars, or None."""
    name = _theme_name()
    path = name and _theme_file(name)
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return title_colours_from(f.read())
    except OSError:
        return None
