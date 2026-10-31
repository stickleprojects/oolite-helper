"""config.toml and layout.toml read through one pydantic model (#135)."""

from dataclasses import replace

import pytest

from helper import settings
from helper.layout import widgets_from_specs, windows_from_specs
from helper.settings import COMPONENTS, Settings, Theme, WindowSettings, check, load, load_layout


def config(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def problems(tmp_path, text, plugins=None):
    with pytest.raises(settings.SettingsError) as error:
        settings.read(config(tmp_path, text), plugins)
    return error.value.problems


# -- [window] ---------------------------------------------------------------


def test_without_a_config_file_everything_is_the_defaults(tmp_path):
    assert load(tmp_path / "missing.toml")[0] == Settings()


def test_window_settings_come_from_its_table(tmp_path):
    loaded = load(config(tmp_path, '[window]\nwidth = "40%"\nanchor = "right"\n'))[0]
    assert (loaded.window.width, loaded.window.anchor) == ("40%", "right")


def test_a_command_line_setting_overrides_the_file(tmp_path):
    loaded = load(config(tmp_path, '[window]\nwidth = "40%"\n'))[0]
    assert loaded.window.changed(width="800").width == "800"


def test_the_laptop_window_is_large_text_by_default():
    assert WindowSettings().layout == "large"


@pytest.mark.parametrize("geometry", ["1200x1000+2640+40", "1200x1000-2640+40"])
def test_a_good_geometry_is_kept(geometry):
    assert WindowSettings(geometry=geometry).geometry == geometry


@pytest.mark.parametrize("geometry", ["1200x1000", "WxH+X+Y", "0x100+0+0"])
def test_a_bad_geometry_is_a_mistake(tmp_path, geometry):
    found = problems(tmp_path, f'[window]\ngeometry = "{geometry}"\n')
    assert found == [f"{tmp_path / 'config.toml'}: [window]: geometry must match WxH+X+Y"]


@pytest.mark.parametrize("font_scale", ["0", "-1", '"large"', "nan", "inf", "true"])
def test_font_scale_must_be_a_positive_number(tmp_path, font_scale):
    found = problems(tmp_path, f"[window]\nfont_scale = {font_scale}\n")
    assert "font_scale must be a positive number" in found[0]


def test_missing_equipment_is_grey_or_hide(tmp_path):
    found = problems(tmp_path, '[window]\nmissing_equipment = "invisible"\n')
    assert "missing_equipment must be one of grey, hide" in found[0]


def test_an_unknown_window_setting_is_a_mistake(tmp_path):
    assert problems(tmp_path, "[window]\nshiny = true\n")[0].endswith(
        "[window]: unknown setting shiny"
    )


# -- [theme] ----------------------------------------------------------------


def test_title_bars_take_the_system_colours_by_default():
    assert Theme() == Theme(title_background="system", title_text="system")


def test_a_title_bar_colour_must_be_system_or_rrggbb(tmp_path):
    found = problems(tmp_path, '[theme]\ntitle_text = "red"\n')
    assert 'title_text must be "system" or a colour like "#cc0000"' in found[0]


def test_system_title_colours_are_the_desktops(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: ("#0055aa", "#ffffff"))
    assert Theme().colours() == ("#0055aa", "#ffffff")


def test_without_desktop_colours_title_bars_are_the_edge_grey(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: None)
    assert Theme().colours() == ("#3c4650", "#e6e6e6")


def test_set_title_colours_replace_the_desktops(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: ("#0055aa", "#ffffff"))
    theme = Theme(title_background="#CC0000", title_text="#FFFFFF")
    assert theme.colours() == ("#cc0000", "#ffffff")


def test_system_text_stays_readable_on_a_set_background(monkeypatch):
    monkeypatch.setattr("helper.desktop.title_colours", lambda: ("#0055aa", "#ffffff"))
    assert Theme(title_background="#eeeeee").colours()[1] == "#000000"


# -- the file as a whole -----------------------------------------------------


def test_an_unknown_table_is_a_mistake(tmp_path):
    found = problems(tmp_path, '[[docks]]\ndock = "game:right"\n')
    assert "unknown table [docks]" in found[0]


def test_every_mistake_is_listed_not_just_the_first(tmp_path):
    text = '[window]\nanchor = "middle"\nmargin = -1\n\n[theme]\ntitle_text = "red"\n'
    assert len(problems(tmp_path, text)) == 3


def test_a_mistake_in_a_widget_names_its_table(tmp_path):
    text = '[[widgets]]\ncomponents = ["drive"]\n\n[[widgets]]\ncomponents = ["tip"]\nx = "a"\n'
    assert problems(tmp_path, text)[0].endswith("widget 2: x must be a whole number of pixels")


def test_a_mistake_in_a_widgetwindows_widget_names_both(tmp_path):
    text = (
        '[[widgetwindows]]\nid = "w"\ntitle = "W"\ndock = "game:right"\nwidth = 600\n'
        'widgets = [{ components = ["drive"] }, { components = ["tip"], layout = "huge" }]\n'
    )
    assert "widgetwindow 1, widget 2: layout must be one of" in problems(tmp_path, text)[0]


# -- what's installed --------------------------------------------------------


def test_a_widget_whose_component_isnt_installed_is_left_out_with_a_warning(tmp_path):
    text = '[[widgets]]\ncomponents = ["drive"]\n\n[[widgets]]\ncomponents = ["lamp"]\n'
    loaded, warnings = load(config(tmp_path, text))
    assert [w.components for w in loaded.widgets] == [("drive",)]
    assert warnings[0].endswith("widget 2: lamp isn't installed, so it's left out")


def test_a_named_widget_that_doesnt_exist_is_left_out_with_a_warning(tmp_path):
    loaded, warnings = load(config(tmp_path, '[[widgets]]\nwidget = "nothing"\n'))
    assert (loaded.widgets, "no widget called 'nothing'" in warnings[0]) == ((), True)


def test_a_plugin_is_a_component_once_its_found(tmp_path):
    loaded, _ = load(config(tmp_path, '[[widgets]]\ncomponents = ["lamp"]\n'), {"lamp": {}})
    assert loaded.widgets[0].components == ("lamp",)


# -- settings components declare (#135) -------------------------------------


@pytest.fixture
def lamp_colour(monkeypatch):
    """The drive component declaring a colour setting."""
    drive = replace(COMPONENTS["drive"], settings={"lamp_colour": "colour"})
    monkeypatch.setitem(COMPONENTS, "drive", drive)


def test_a_setting_its_component_declares_is_allowed(tmp_path, lamp_colour):
    text = '[[widgets]]\ncomponents = ["drive"]\nlamp_colour = "#00ff00"\n'
    assert load(config(tmp_path, text))[0].widgets[0].extras == {"lamp_colour": "#00ff00"}


def test_a_declared_setting_must_be_its_type(tmp_path, lamp_colour):
    text = '[[widgets]]\ncomponents = ["drive"]\nlamp_colour = "green"\n'
    assert problems(tmp_path, text)[0].endswith('lamp_colour must be a colour like "#cc0000"')


def test_a_setting_nothing_declares_is_a_mistake(tmp_path):
    text = '[[widgets]]\ncomponents = ["drive"]\nlamp_colour = "#00ff00"\n'
    assert problems(tmp_path, text)[0].endswith("widget 1: unknown setting lamp_colour")


def test_a_setting_a_plugin_declares_is_allowed(tmp_path):
    text = '[[widgets]]\ncomponents = ["lamp"]\nbrightness = 3\n'
    loaded, _ = load(config(tmp_path, text), {"lamp": {"brightness": "whole"}})
    assert loaded.widgets[0].extras == {"brightness": 3}


# -- layout.toml -------------------------------------------------------------

TRADING = (
    '[[widgetwindows]]\nid = "trading"\ntitle = "Trading"\ndock = "game:right"\nwidth = 640\n'
    'widgets = [{ components = ["trade_here"] }]\n'
)


def laid_out(tmp_path, layout_text):
    loaded = load(config(tmp_path, TRADING))[0]
    widgets = widgets_from_specs(loaded.all_widgets)
    windows = windows_from_specs(loaded.widgetwindows, widgets)
    path = tmp_path / "layout.toml"
    path.write_text(layout_text, encoding="utf-8")
    return load_layout(widgets, windows, path)


def test_layout_tomls_changes_go_on_top(tmp_path):
    _, windows, warnings = laid_out(tmp_path, '[widgets."trading"]\nwidth = 700\n')
    assert (windows[0].spec.width, warnings) == (700, [])


def test_a_bad_layout_toml_is_ignored_whole_with_a_warning_for_each_problem(tmp_path):
    text = '[widgets."trading"]\nwidth = 700\ndock = "game:middle"\nshiny = 1\n'
    _, windows, warnings = laid_out(tmp_path, text)
    assert windows[0].spec.width == 640
    assert len(warnings) == 3  # shiny, dock, and that the file was ignored


def test_check_lists_the_problems_in_both_files(tmp_path):
    path = config(tmp_path, TRADING + '\n[theme]\ntitle_text = "red"\n')
    assert len(check(path, tmp_path / "layout.toml")) == 1


def test_check_finds_nothing_wrong_with_good_files(tmp_path):
    assert check(config(tmp_path, TRADING), tmp_path / "layout.toml") == []


def test_a_mistake_after_a_left_out_widget_keeps_its_number_in_the_file(tmp_path):
    text = '[[widgets]]\ncomponents = ["lamp"]\n\n[[widgets]]\ncomponents = ["drive"]\nx = "a"\n'
    assert problems(tmp_path, text)[0].endswith("widget 2: x must be a whole number of pixels")


def test_check_lists_widgets_left_out_alongside_the_mistakes(tmp_path):
    path = config(tmp_path, '[[widgets]]\ncomponents = ["lamp"]\n\n[window]\nmargin = -1\n')
    assert len(check(path, tmp_path / "layout.toml")) == 2


def test_check_lists_the_problems_in_layout_toml(tmp_path):
    (tmp_path / "layout.toml").write_text('[widgets."trading"]\nwidth = -5\n')
    found = check(config(tmp_path, TRADING), tmp_path / "layout.toml")
    assert "trading: width must be pixels or a percentage" in found[0]
