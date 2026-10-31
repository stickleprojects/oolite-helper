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
missing_equipment = "grey"  # or "hide": keys for equipment you haven't got
ui = "web"            # widgets as web views; "tk" for the old Tk widgets (the fallback)
# geometry = "1200x1000+2640+40"   # exact X geometry; overrides the above

[theme]
title_background = "system"  # widgets' title bars: the desktop's colour, or "#cc0000"
title_text = "system"        # their text: the desktop's colour, or "#ffffff"
"""

import math
import os
import re
import tomllib
from collections.abc import Mapping

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
    "missing_equipment": "grey",
    "ui": "web",
}
LAYOUTS = ("large", "compact")
MISSING_EQUIPMENT = ("grey", "hide")
UIS = ("web", "tk")
THEME_DEFAULTS = {"title_background": "system", "title_text": "system"}
_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")
_GEOMETRY = re.compile(r"[1-9]\d*x[1-9]\d*[+-]\d+[+-]\d+")


def load_window_settings(
    path: str | os.PathLike[str] = PATH, overrides: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Defaults, then the config file's [window] table, then non-None overrides."""
    settings: dict[str, object] = dict(WINDOW_DEFAULTS)
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
    if settings["missing_equipment"] not in MISSING_EQUIPMENT:
        raise SystemExit(
            f"missing_equipment must be one of {', '.join(MISSING_EQUIPMENT)}, "
            f"not {settings['missing_equipment']!r}"
        )
    if settings["ui"] not in UIS:
        raise SystemExit(f"ui must be one of {', '.join(UIS)}, not {settings['ui']!r}")
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


def load_theme(path: str | os.PathLike[str] = PATH) -> dict[str, str]:
    """The [theme] table (#122): each colour "system" (the desktop's) or "#rrggbb"."""
    theme = dict(THEME_DEFAULTS)
    if os.path.exists(path):
        with open(path, "rb") as f:
            table = tomllib.load(f).get("theme", {})
        unknown = set(table) - set(THEME_DEFAULTS)
        if unknown:
            raise SystemExit(f"{path}: unknown [theme] settings: {', '.join(sorted(unknown))}")
        theme.update(table)
    for key, value in theme.items():
        if value != "system" and not (isinstance(value, str) and _COLOUR.fullmatch(value)):
            raise SystemExit(f'{key} must be "system" or a colour like "#cc0000", not {value!r}')
    return theme
