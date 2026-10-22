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

CACHE = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "oolite-helper"
)
CONFIG_IN_APPIMAGE = "usr/bin/Resources/Config"
NEEDED = ("keyconfig2.plist", "descriptions.plist")

KEY_NAMES = {
    "arrowLeft": "←",
    "arrowRight": "→",
    "arrowUp": "↑",
    "arrowDown": "↓",
    "pageUp": "PgUp",
    "pageDown": "PgDn",
    "home": "Home",
    "end": "End",
    "tab": "Tab",
    "enter": "Enter",
    "esc": "Esc",
    "space": "Space",
    " ": "Space",
    "numpadEnter": "Num Enter",
    "insert": "Ins",
    "delete": "Del",
    "backspace": "Backspace",
    "pause": "Pause",
    "printScreen": "PrtSc",
    "/": "Slash",  # alternatives are joined with " / ", so "/ / Num /" was unreadable (#4)
}

# In-game key changes are saved with a numeric key code (src/SDL/MyOpenGLView.h,
# enum GameViewKeys). Codes below 256 are the character itself; these are the
# rest, as the names keyconfig2.plist uses.
SPECIAL_CODES = {
    **{256 + i: f"f{i + 1}" for i in range(11)},
    267: "arrowRight",
    268: "arrowLeft",
    269: "arrowDown",
    270: "arrowUp",
    271: "pause",
    272: "printScreen",
    303: "home",
    304: "end",
    305: "insert",
    306: "delete",
    307: "pageUp",
    308: "pageDown",
    309: "backspace",
    **{310 + i: f"numpad{i}" for i in range(10)},
    320: "numpad/",
    321: "numpad*",
    322: "numpad-",
    323: "numpad+",
    324: "numpad.",
    325: "numpad=",
    326: "numpadEnter",
}
CHAR_NAMES = {9: "tab", 13: "enter", 27: "esc", 32: "space"}


class Keymap:
    def __init__(self, bindings, descriptions, commodities=None):
        self.bindings = bindings  # action -> list of entry dicts
        self.descriptions = descriptions  # action -> text
        self.commodities = commodities or {}  # commodity key -> display name

    def keys(self, action):
        """Display text for an action's keys, e.g. "Shift+L", or "" if unbound."""
        return " / ".join(format_entry(e) for e in self.bindings.get(action, []))

    def describe(self, action):
        return self.descriptions.get(action, action.removeprefix("key_").replace("_", " "))

    def commodity(self, key):
        """A commodity's name as the game shows it, e.g. "gem_stones" -> "Gem-Stones"."""
        return self.commodities.get(key) or commodity_fallback(key)


def commodity_fallback(key):
    return key.replace("_", " ").title()


def is_on(value):
    """True for a modifier flag in any saved form: "true", "YES", "1", 1, True."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def decode_key(key):
    """A saved key (a name, or a numeric code from an in-game change) as a name."""
    if isinstance(key, str) and not key.isdigit():
        return key
    code = int(key)
    if code in SPECIAL_CODES:
        return SPECIAL_CODES[code]
    if code in CHAR_NAMES:
        return CHAR_NAMES[code]
    if 32 < code < 256:
        return chr(code)
    return str(code)


def from_override(entry):
    """An in-game key change (numeric key, 1/0 flags) as a keyconfig2-style entry."""
    out = dict(entry)
    if "key" in out:
        out["key"] = decode_key(out["key"])
    return out


def format_entry(entry):
    key = str(entry.get("key", "?"))
    mods = []
    if is_on(entry.get("mod1")):
        mods.append("Ctrl")
    if is_on(entry.get("mod2")):
        mods.append("Alt")
    # Symbols like + * _ ? carry shift=true because that's how they're typed;
    # "Shift++" would mislead, so only letters and named keys show Shift.
    symbol = len(key) == 1 and not key.isalnum()
    if (is_on(entry.get("shift")) and not symbol) or (len(key) == 1 and key.isupper()):
        mods.append("Shift")
    if key in KEY_NAMES:
        name = KEY_NAMES[key]
    elif key.startswith("numpad"):
        name = "Num " + key[len("numpad") :]
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
    for action, entries in settings.get("KeyConfigOverrides", {}).items():  # in-game changes
        bindings[action] = [from_override(e) for e in entries]

    prefix = "oolite-keydesc-"
    descriptions = {k[len(prefix) :]: v for k, v in texts.items() if k.startswith(prefix)}
    names = "commodity-name "
    commodities = {k[len(names) :]: v for k, v in texts.items() if k.startswith(names)}
    return Keymap(bindings, descriptions, commodities)


def _extracted_config(appimage):
    """Directory holding NEEDED files from the AppImage, extracting if stale."""
    stamp = str(int(os.stat(appimage).st_mtime))
    root = os.path.join(CACHE, os.path.basename(appimage) + "-" + stamp)
    config_dir = os.path.join(root, "squashfs-root", CONFIG_IN_APPIMAGE)
    if all(os.path.exists(os.path.join(config_dir, n)) for n in NEEDED):
        return config_dir
    os.makedirs(root, exist_ok=True)
    for name in NEEDED:
        subprocess.run(
            [appimage, "--appimage-extract", f"{CONFIG_IN_APPIMAGE}/{name}"],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return config_dir
