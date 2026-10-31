"""Where the game lives. Override with the same variables launch-oolite.sh uses."""

import os

APPIMAGE = os.environ.get(
    "OOLITE_APPIMAGE", os.path.expanduser("~/Games/Oolite/oolite-1.92.1-x86_64.AppImage")
)
GAME_DATA = os.environ.get("OOLITE_GAMEDATA", os.path.join(os.path.dirname(APPIMAGE), "GameData"))

LOG = os.path.join(GAME_DATA, "Logs", "Latest.log")
SETTINGS = os.path.join(GAME_DATA, "Settings", "OoliteDefaults.plist")

# The helper's own settings (#135): config.toml, written by the player, and
# layout.toml beside it, written by the helper (see helper/settings.py).
CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "oolite-helper"
)
CONFIG = os.path.join(CONFIG_DIR, "config.toml")
LAYOUT = os.path.join(CONFIG_DIR, "layout.toml")
