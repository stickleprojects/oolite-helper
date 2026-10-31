"""Everything tied to the operating system and desktop (#140), in one place.

The rest of the helper imports these names from here, never from an
implementation, so porting the helper (e.g. to Windows, #139) means adding one
module beside linux_x11 that provides the same names:

- CONFIG_DIR, CACHE_DIR, DATA_DIR: the helper's own folders (config.toml and
  plugins; caches; remembered markets).
- LOG: the game's Latest.log. SETTINGS: the game's settings plist, with the
  player's keyboard layout and KeyConfigOverrides.
- game_config_dir(): a folder holding the game's keyconfig2.plist and
  descriptions.plist.
- list_monitors(): a screen.Monitor for each monitor ([] if unknown).
- GameWindow(): its poll() returns a "window/game" action: the game window's
  client rect (or None), its window-manager borders and whether it's active.
- title_colours(): (background, text) of the desktop's title bars, or None.
- single_instance_lock(): an open lock held for the life of the process, or
  None if another helper holds it.

The web host (helper/webhost/host.py) is tied to GTK and WebKitGTK too, but
it's a separate process behind PROTOCOL, so another system can bring its own.
"""

import sys

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

if sys.platform.startswith("linux"):
    from .linux_x11 import (
        CACHE_DIR,
        CONFIG_DIR,
        DATA_DIR,
        LOG,
        SETTINGS,
        GameWindow,
        game_config_dir,
        list_monitors,
        single_instance_lock,
        title_colours,
    )
else:
    raise ImportError(
        f"oolite-helper doesn't run on {sys.platform!r} yet: add a module to helper/platform/ "
        f"that provides {', '.join(__all__)} (see helper/platform/__init__.py and #139)"
    )
