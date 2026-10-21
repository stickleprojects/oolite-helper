"""Window placement: which monitor, how big, and where on it."""

import re
import subprocess
from dataclasses import dataclass

ANCHORS = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)

# e.g. " 1: +eDP-1 1920/293x1080/165+960+1080  eDP-1"
_MONITOR_RE = re.compile(r"^\s*\d+:\s+\+?(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)")


@dataclass
class Monitor:
    name: str
    primary: bool
    width: int
    height: int
    x: int
    y: int

    def __str__(self):
        flag = " (primary)" if self.primary else ""
        return f"{self.name}: {self.width}x{self.height}+{self.x}+{self.y}{flag}"


def list_monitors():
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    monitors = []
    for line in out.splitlines():
        m = _MONITOR_RE.match(line)
        if m:
            star, name, w, h, x, y = m.groups()
            monitors.append(Monitor(name, star == "*", int(w), int(h), int(x), int(y)))
    return monitors


def choose_monitor(monitors, name=None):
    """The named monitor, else the first non-primary one, else the primary."""
    if name:
        for m in monitors:
            if m.name == name:
                return m
        names = ", ".join(m.name for m in monitors) or "none found"
        raise SystemExit(f"Screen {name!r} not found (available: {names})")
    others = [m for m in monitors if not m.primary]
    return (others or monitors or [None])[0]


def _length(value, total):
    """'60%' -> share of total; '800' or 800 -> pixels (capped at total)."""
    text = str(value).strip()
    if text.endswith("%"):
        return round(total * float(text[:-1]) / 100)
    return min(int(text), total)


def geometry(monitor, width="100%", height="100%", anchor="top-left", margin=0):
    """X geometry string (WxH+X+Y) for a window placed on monitor."""
    if anchor not in ANCHORS:
        raise SystemExit(f"Unknown anchor {anchor!r} (use one of: {', '.join(ANCHORS)})")
    avail_w = monitor.width - 2 * margin
    avail_h = monitor.height - 2 * margin
    w, h = _length(width, avail_w), _length(height, avail_h)

    if anchor.endswith("left") or anchor == "left":
        x = margin
    elif anchor.endswith("right") or anchor == "right":
        x = monitor.width - margin - w
    else:
        x = (monitor.width - w) // 2
    if anchor.startswith("top"):
        y = margin
    elif anchor.startswith("bottom"):
        y = monitor.height - margin - h
    else:
        y = (monitor.height - h) // 2
    return f"{w}x{h}+{monitor.x + x}+{monitor.y + y}"
