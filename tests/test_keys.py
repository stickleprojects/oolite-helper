import os
from pathlib import Path

import pytest

from helper import keys, plist

FIXTURE = Path(__file__).parent / "fixtures" / "keyconfig2.plist"


def test_format_entry_modifiers_symbols_and_uppercase_keys():
    assert (
        keys.format_entry({"key": "L", "shift": "true", "mod1": "true", "mod2": "true"})
        == "Ctrl+Alt+Shift+L"
    )
    assert keys.format_entry({"key": "C"}) == "Shift+C"
    for symbol in ("+", "*", "_"):
        assert keys.format_entry({"key": symbol, "shift": "true"}) == symbol


def test_format_entry_named_numpad_and_function_keys():
    assert keys.format_entry({"key": "arrowLeft"}) == "←"
    assert keys.format_entry({"key": "pageDown"}) == "PgDn"
    assert keys.format_entry({"key": "numpadEnter"}) == "Num Enter"
    assert keys.format_entry({"key": "numpad7"}) == "Num 7"
    assert keys.format_entry({"key": "f1"}) == "F1"


def test_load_keymap_merges_default_layout_then_overrides(tmp_path, monkeypatch):
    settings = tmp_path / "OoliteDefaults.plist"
    settings.write_text(
        """{
            "keyboard-code" = "deu";
            KeyConfigOverrides = {
                key_hyperspace = ({ key = "x"; });
            };
        }""",
        encoding="utf-8",
    )
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "keyconfig2.plist").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    keyconfig = plist.load(FIXTURE)
    (config_dir / "descriptions.plist").write_text(
        '{ "oolite-keydesc-key_hyperspace" = "Hyperspace"; }',
        encoding="utf-8",
    )
    monkeypatch.setattr(keys, "_extracted_config", lambda appimage: str(config_dir))
    keymap = keys.load_keymap("unused", str(settings))

    assert keymap.bindings["key_roll_left"] == keyconfig["default"]["key_roll_left"]
    assert keymap.keys("key_next_compass_mode") == "Alt+\\"
    assert keymap.keys("key_hyperspace") == "X"
    assert keymap.describe("key_hyperspace") == "Hyperspace"


def test_extracted_config_refreshes_when_appimage_changes(tmp_path, monkeypatch):
    appimage = tmp_path / "oolite.AppImage"
    appimage.touch()
    monkeypatch.setattr(keys, "CACHE", str(tmp_path / "cache"))
    calls = []

    def extract(args, cwd, **kwargs):
        calls.append(args[-1])
        config_dir = Path(cwd) / "squashfs-root" / keys.CONFIG_IN_APPIMAGE
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

    monkeypatch.setattr(keys.subprocess, "run", extract)
    os.utime(appimage, (1_000_000_000, 1_000_000_000))
    first = keys._extracted_config(str(appimage))
    assert len(calls) == 2

    os.utime(appimage, (1_000_000_002, 1_000_000_002))
    second = keys._extracted_config(str(appimage))
    assert second != first
    assert len(calls) == 4


def test_real_in_game_remap_shows_ctrl_alt_quote(tmp_path, monkeypatch):
    # Saved by 1.92.1 after remapping docking clearance in-game (#26).
    remap = Path(__file__).parent / "fixtures" / "OoliteDefaults-remap.plist"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "keyconfig2.plist").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (config_dir / "descriptions.plist").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(keys, "_extracted_config", lambda appimage: str(config_dir))
    keymap = keys.load_keymap("unused", str(remap))
    assert keymap.keys("key_docking_clearance_request") == 'Ctrl+Alt+"'


@pytest.mark.parametrize(
    ("entry", "shown"),
    [
        ({"key": "268"}, "←"),
        ({"key": "260"}, "F5"),
        ({"key": "326"}, "Num Enter"),
        ({"key": "313"}, "Num 3"),
        ({"key": "306", "mod1": "1"}, "Ctrl+Del"),
        ({"key": "107", "shift": "1"}, "Shift+K"),
        ({"key": "107"}, "K"),
        ({"key": "9"}, "Tab"),
        ({"key": "32"}, "Space"),
        ({"key": "x"}, "X"),
    ],
)
def test_in_game_key_codes(entry, shown):
    assert keys.format_entry(keys.from_override(entry)) == shown


@pytest.mark.parametrize("on", ["true", "TRUE", "yes", "YES", "1", 1, True])
def test_modifier_saved_forms_count_as_on(on):
    assert keys.format_entry({"key": "k", "shift": on, "mod1": on}) == "Ctrl+Shift+K"


@pytest.mark.parametrize("off", ["false", "NO", "0", 0, False, None])
def test_modifier_saved_forms_count_as_off(off):
    assert keys.format_entry({"key": "k", "shift": off}) == "K"
