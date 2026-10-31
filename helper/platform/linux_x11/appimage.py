"""The game's config files, extracted from inside the Oolite AppImage.

They're extracted once into a cache that's refreshed whenever the AppImage
changes.
"""

import os
import shutil
import subprocess

CONFIG_IN_APPIMAGE = "usr/bin/Resources/Config"
NEEDED = ("keyconfig2.plist", "descriptions.plist")


def extracted_config(appimage, cache):
    """Directory holding NEEDED files from the AppImage, extracting if stale."""
    stamp = str(int(os.stat(appimage).st_mtime))
    root = os.path.join(cache, os.path.basename(appimage) + "-" + stamp)
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
    _prune_old_caches(appimage, root, cache)
    return config_dir


def _prune_old_caches(appimage, root, cache):
    """Remove extractions of earlier versions of this AppImage. Best effort: a
    folder that can't be removed mustn't stop the keys loading."""
    prefix = os.path.basename(appimage) + "-"
    try:
        with os.scandir(cache) as entries:
            for entry in entries:
                if (
                    entry.name.startswith(prefix)
                    and entry.name != os.path.basename(root)
                    and entry.is_dir(follow_symlinks=False)
                ):
                    shutil.rmtree(entry.path, ignore_errors=True)
    except OSError:
        pass
