"""Where the game lives. Override with the same variables launch-oolite.sh uses."""

import os

APPIMAGE = os.environ.get(
    "OOLITE_APPIMAGE", os.path.expanduser("~/Games/Oolite/oolite-1.92.1-x86_64.AppImage"))
GAME_DATA = os.environ.get(
    "OOLITE_GAMEDATA", os.path.join(os.path.dirname(APPIMAGE), "GameData"))

LOG = os.path.join(GAME_DATA, "Logs", "Latest.log")
SETTINGS = os.path.join(GAME_DATA, "Settings", "OoliteDefaults.plist")
