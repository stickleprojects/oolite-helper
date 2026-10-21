"""The player's real key bindings, read from the game's files on helper startup.

Built-in bindings and descriptions come from inside the AppImage. They're
extracted once into a cache that's refreshed whenever the AppImage changes.
The player's layout choice and in-game key changes come from the settings file
and are read every time.
"""

import os
import subprocess

from . import plist
from .paths import APPIMAGE, SETTINGS

CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                     "oolite-helper")
CONFIG_IN_APPIMAGE = "usr/bin/Resources/Config"
NEEDED = ("keyconfig2.plist", "descriptions.plist")

KEY_NAMES = {
    "arrowLeft": "←", "arrowRight": "→", "arrowUp": "↑", "arrowDown": "↓",
    "pageUp": "PgUp", "pageDown": "PgDn", "home": "Home", "end": "End",
    "tab": "Tab", "enter": "Enter", "esc": "Esc", "space": "Space", " ": "Space",
    "numpadEnter": "Num Enter",
}


class Keymap:
    def __init__(self, bindings, descriptions):
        self.bindings = bindings          # action -> list of entry dicts
        self.descriptions = descriptions  # action -> text

    def keys(self, action):
        """Display text for an action's keys, e.g. "Shift+L", or "" if unbound."""
        return " / ".join(format_entry(e) for e in self.bindings.get(action, []))

    def describe(self, action):
        return self.descriptions.get(action, action.removeprefix("key_").replace("_", " "))


def format_entry(entry):
    key = entry.get("key", "?")
    mods = []
    if entry.get("mod1") == "true":
        mods.append("Ctrl")
    if entry.get("mod2") == "true":
        mods.append("Alt")
    # Symbols like + * _ ? carry shift=true because that's how they're typed;
    # "Shift++" would mislead, so only letters and named keys show Shift.
    symbol = len(key) == 1 and not key.isalnum()
    if (entry.get("shift") == "true" and not symbol) or (len(key) == 1 and key.isupper()):
        mods.append("Shift")
    if key in KEY_NAMES:
        name = KEY_NAMES[key]
    elif key.startswith("numpad"):
        name = "Num " + key[len("numpad"):]
    else:
        name = key.upper()  # letters, digits, symbols, f1-f12
    return "+".join(mods + [name])


def load_keymap(appimage=APPIMAGE, settings_path=SETTINGS):
    config_dir = _extracted_config(appimage)
    keyconfig = plist.load(os.path.join(config_dir, "keyconfig2.plist"))
    texts = plist.load(os.path.join(config_dir, "descriptions.plist"))

    settings = {}
    if os.path.exists(settings_path):
        settings = plist.load(settings_path)

    layout = settings.get("keyboard-code", "default")
    bindings = dict(keyconfig.get("default", {}))
    if layout != "default":
        bindings.update(keyconfig.get(layout, {}))
    bindings.update(settings.get("KeyConfigOverrides", {}))  # in-game key changes

    prefix = "oolite-keydesc-"
    descriptions = {k[len(prefix):]: v for k, v in texts.items() if k.startswith(prefix)}
    return Keymap(bindings, descriptions)


def _extracted_config(appimage):
    """Directory holding NEEDED files from the AppImage, extracting if stale."""
    stamp = str(int(os.stat(appimage).st_mtime))
    root = os.path.join(CACHE, os.path.basename(appimage) + "-" + stamp)
    config_dir = os.path.join(root, "squashfs-root", CONFIG_IN_APPIMAGE)
    if all(os.path.exists(os.path.join(config_dir, n)) for n in NEEDED):
        return config_dir
    os.makedirs(root, exist_ok=True)
    for name in NEEDED:
        subprocess.run([appimage, "--appimage-extract", f"{CONFIG_IN_APPIMAGE}/{name}"],
                       cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return config_dir
