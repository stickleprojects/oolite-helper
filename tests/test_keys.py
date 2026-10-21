import os
from pathlib import Path

from helper import keys, plist


FIXTURE = Path(__file__).parent / "fixtures" / "keyconfig2.plist"


def test_format_entry_modifiers_symbols_and_uppercase_keys():
    assert keys.format_entry(
        {"key": "L", "shift": "true", "mod1": "true", "mod2": "true"}
    ) == "Ctrl+Alt+Shift+L"
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
        '''{
            "keyboard-code" = "deu";
            KeyConfigOverrides = {
                key_hyperspace = ({ key = "x"; });
            };
        }''',
        encoding="utf-8",
    )
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "keyconfig2.plist").write_text(FIXTURE.read_text(encoding="utf-8"),
                                                encoding="utf-8")
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
