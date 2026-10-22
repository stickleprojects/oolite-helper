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


def test_layout_defaults_to_large_and_rejects_unknown_names(tmp_path):
    import pytest

    from helper.config import load_window_settings

    missing = tmp_path / "none.toml"
    assert load_window_settings(missing)["layout"] == "large"
    assert load_window_settings(missing, {"layout": "compact"})["layout"] == "compact"
    bad = tmp_path / "config.toml"
    bad.write_text('[window]\nlayout = "tiny"\n')
    with pytest.raises(SystemExit, match="layout must be one of"):
        load_window_settings(bad)


@pytest.mark.parametrize("geometry", ["1200x1000+2640+40", "1200x1000-2640+40"])
def test_valid_geometry_is_accepted(tmp_path, geometry):
    assert (
        config.load_window_settings(tmp_path / "missing.toml", {"geometry": geometry})["geometry"]
        == geometry
    )


@pytest.mark.parametrize("geometry", ["1200x1000", "WxH+X+Y", "0x100+0+0", 123])
def test_invalid_geometry_is_rejected(tmp_path, geometry):
    with pytest.raises(SystemExit, match="geometry must match WxH\\+X\\+Y"):
        config.load_window_settings(tmp_path / "missing.toml", {"geometry": geometry})


@pytest.mark.parametrize("font_scale", [0, -1, "large", "nan", float("inf"), True])
def test_invalid_font_scale_is_rejected(tmp_path, font_scale):
    with pytest.raises(SystemExit, match="font_scale must be a positive number"):
        config.load_window_settings(tmp_path / "missing.toml", {"font_scale": font_scale})
