"""Linux with X11 (#140): what helper.platform provides here.

Folders follow the XDG variables. The game is the Oolite AppImage, with its
data folder beside it (as scripts/launch-oolite.sh sets up); both can be
moved with the same variables that script uses. Windows and monitors come
from xdotool, xwininfo, xprop and xrandr, and title bar colours from the
Marco/Metacity window theme.
"""

import fcntl
import os
import tempfile

from .appimage import extracted_config
from .desktop import title_colours
from .gamewindow import GameWindow
from .monitors import list_monitors


def _xdg(variable, default):
    return os.path.join(os.environ.get(variable) or os.path.expanduser(default), "oolite-helper")


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", "~/.config")
CACHE_DIR = _xdg("XDG_CACHE_HOME", "~/.cache")
DATA_DIR = _xdg("XDG_DATA_HOME", "~/.local/share")

APPIMAGE = os.environ.get(
    "OOLITE_APPIMAGE", os.path.expanduser("~/Games/Oolite/oolite-1.92.1-x86_64.AppImage")
)
GAME_DATA = os.environ.get("OOLITE_GAMEDATA", os.path.join(os.path.dirname(APPIMAGE), "GameData"))
LOG = os.path.join(GAME_DATA, "Logs", "Latest.log")
SETTINGS = os.path.join(GAME_DATA, "Settings", "OoliteDefaults.plist")


def game_config_dir():
    """A folder holding the game's keyconfig2.plist and descriptions.plist."""
    return extracted_config(APPIMAGE, CACHE_DIR)


def single_instance_lock():
    """Hold an exclusive lock for the life of the process; None if another helper has it."""
    path = os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()), "oolite-helper.lock"
    )
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


__all__ = [
    "CACHE_DIR",
    "CONFIG_DIR",
    "DATA_DIR",
    "LOG",
    "SETTINGS",
    "GameWindow",
    "game_config_dir",
    "list_monitors",
    "single_instance_lock",
    "title_colours",
]
