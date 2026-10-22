"""User settings from ~/.config/oolite-helper/config.toml (all optional).

[window]
screen = "HDMI-1"     # xrandr name; default: first non-primary monitor
width = "40%"         # pixels or % of that screen
height = "100%"
anchor = "right"      # top-left, top, top-right, left, center, right,
                      # bottom-left, bottom, bottom-right
margin = 0            # pixels from the screen edges
layout = "large"      # or "compact": smaller text and spacing, up to 6 key columns
font_scale = 1.0      # multiplies the layout's text size
# geometry = "1200x1000+2640+40"   # exact X geometry; overrides the above
"""

import math
import os
import re
import tomllib

PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "oolite-helper",
    "config.toml",
)

WINDOW_DEFAULTS = {
    "screen": None,
    "width": "100%",
    "height": "100%",
    "anchor": "top-left",
    "margin": 0,
    "layout": "large",
    "font_scale": 1.0,
    "geometry": None,
}
LAYOUTS = ("large", "compact")
_GEOMETRY = re.compile(r"[1-9]\d*x[1-9]\d*[+-]\d+[+-]\d+")


def load_window_settings(path=PATH, overrides=None):
    """Defaults, then the config file's [window] table, then non-None overrides."""
    settings = dict(WINDOW_DEFAULTS)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = tomllib.load(f)
        unknown = set(data.get("window", {})) - set(WINDOW_DEFAULTS)
        if unknown:
            raise SystemExit(f"{path}: unknown [window] settings: {', '.join(sorted(unknown))}")
        settings.update(data.get("window", {}))
    for key, value in (overrides or {}).items():
        if value is not None:
            settings[key] = value
    if settings["layout"] not in LAYOUTS:
        raise SystemExit(f"layout must be one of {', '.join(LAYOUTS)}, not {settings['layout']!r}")
    geometry = settings["geometry"]
    if geometry is not None and (
        not isinstance(geometry, str) or not _GEOMETRY.fullmatch(geometry)
    ):
        raise SystemExit(f"geometry must match WxH+X+Y, not {geometry!r}")
    font_scale = settings["font_scale"]
    if (
        isinstance(font_scale, bool)
        or not isinstance(font_scale, (int, float))
        or not math.isfinite(font_scale)
        or font_scale <= 0
    ):
        raise SystemExit(f"font_scale must be a positive number, not {font_scale!r}")
    return settings
