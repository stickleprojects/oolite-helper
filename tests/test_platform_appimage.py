"""The game's config files, extracted from the AppImage (Linux)."""

import os
from pathlib import Path

from helper.platform.linux_x11 import appimage as appimage_files


def test_extracted_config_refreshes_when_appimage_changes(tmp_path, monkeypatch):
    appimage = tmp_path / "oolite.AppImage"
    appimage.touch()
    cache = tmp_path / "cache"
    cache.mkdir()
    stale_cache = cache / "oolite.AppImage-9999999999"
    stale_cache.mkdir()
    other_cache = cache / "other.AppImage-9999999999"
    other_cache.mkdir()
    outside_cache = tmp_path / "outside-cache"
    outside_cache.mkdir()
    calls = []

    def extract(args, cwd, **kwargs):
        calls.append(args[-1])
        config_dir = Path(cwd) / "squashfs-root" / appimage_files.CONFIG_IN_APPIMAGE
        config_dir.mkdir(parents=True, exist_ok=True)
        if args[-1].endswith("keyconfig2.plist"):
            (config_dir / "keyconfig2.plist").write_text(
                '{ default = { key_fire_lasers = ({ key = "a"; }); }; }',
                encoding="utf-8",
            )
        else:
            (config_dir / "descriptions.plist").write_text(
                '{ "oolite-keydesc-key_fire_lasers" = "Fire"; }',
                encoding="utf-8",
            )

    monkeypatch.setattr(appimage_files.subprocess, "run", extract)
    os.utime(appimage, (1_000_000_000, 1_000_000_000))
    first = appimage_files.extracted_config(str(appimage), str(cache))
    first_root = Path(first).parents[4]
    assert len(calls) == 2
    assert not stale_cache.exists()
    assert other_cache.exists()
    assert outside_cache.exists()

    os.utime(appimage, (1_000_000_002, 1_000_000_002))
    second = appimage_files.extracted_config(str(appimage), str(cache))
    assert second != first
    assert len(calls) == 4
    assert not first_root.exists()
    assert other_cache.exists()


def test_a_cache_that_cannot_be_pruned_does_not_stop_the_keys_loading(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()

    def broken_scandir(path):
        raise PermissionError(path)

    monkeypatch.setattr(appimage_files.os, "scandir", broken_scandir)
    appimage = str(tmp_path / "oolite.AppImage")
    appimage_files._prune_old_caches(appimage, str(cache / "x"), str(cache))  # no error
