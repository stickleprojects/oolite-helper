"""Where the game's and the helper's files are. The folders come from helper.platform."""

import os

from .platform import CONFIG_DIR, LOG, SETTINGS

__all__ = ["CONFIG", "CONFIG_DIR", "LAYOUT", "LOG", "SETTINGS"]

# The helper's own settings (#135): config.toml, written by the player, and
# layout.toml beside it, written by the helper (see helper/settings.py).
CONFIG = os.path.join(CONFIG_DIR, "config.toml")
LAYOUT = os.path.join(CONFIG_DIR, "layout.toml")
