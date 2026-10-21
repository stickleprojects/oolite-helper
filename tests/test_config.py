import pytest

from helper import config


def test_defaults_without_config_file(tmp_path):
    assert config.load_window_settings(tmp_path / "missing.toml") == config.WINDOW_DEFAULTS


def test_config_file_then_cli_override_precedence(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[window]\nwidth = "40%"\nanchor = "right"\nfont_scale = 0.8\n',
        encoding="utf-8",
    )
    result = config.load_window_settings(path, {"width": "800", "anchor": None, "font_scale": 1.2})
    assert result == {
        **config.WINDOW_DEFAULTS,
        "width": "800",
        "anchor": "right",
        "font_scale": 1.2,
    }


def test_unknown_window_keys_are_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[window]\nunknown = true\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="unknown \\[window\\] settings: unknown"):
        config.load_window_settings(path)
