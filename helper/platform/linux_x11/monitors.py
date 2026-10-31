"""The monitors, from xrandr."""

import re
import subprocess

from ...screen import Monitor

# e.g. " 1: +eDP-1 1920/293x1080/165+960+1080  eDP-1"
_MONITOR_RE = re.compile(r"^\s*\d+:\s+\+?(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)")


def list_monitors() -> list[Monitor]:
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    monitors: list[Monitor] = []
    for line in out.splitlines():
        m = _MONITOR_RE.match(line)
        if m:
            star, name, w, h, x, y = m.groups()
            monitors.append(Monitor(name, star == "*", int(w), int(h), int(x), int(y)))
    return monitors
