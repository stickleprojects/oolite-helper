import pytest

from helper.model import Model
from helper.screen import Monitor
from helper.widgets import PRESETS, WidgetSpec, load_widgets, place, read_preset

GAME = ((1282, 204, 1280, 720), (2, 2, 24, 2), True)  # geometry, frame, active


def test_docked_widgets_sit_outside_the_game_window():
    top = WidgetSpec(components=("drive",), dock="game:top")
    assert place(top, GAME, (300, 30)) == (1282, 204 - 24 - 30, 1280, 30)  # above the title bar
    bottom = WidgetSpec(components=("drive",), dock="game:bottom", height=40)
    assert place(bottom, GAME, (300, 30)) == (1282, 204 + 720 + 2, 1280, 40)
    right = WidgetSpec(components=("trade_here",), dock="game:right", width=520)
    assert place(right, GAME, (400, 300)) == (1282 + 1280 + 2, 204, 520, 720)
    left = WidgetSpec(components=("trade_here",), dock="game:left", x=-10)
    assert place(left, GAME, (400, 300)) == (1282 - 2 - 400 - 10, 204, 400, 720)


def test_docked_widgets_hide_unless_the_game_is_the_active_window():
    spec = WidgetSpec(components=("drive",), dock="game:top")
    assert place(spec, (GAME[0], GAME[1], False), (300, 30)) is None
    assert place(spec, (None, (0, 0, 0, 0), False), (300, 30)) is None
    always = WidgetSpec(components=("drive",), dock="game:top", show="always")
    assert place(always, (GAME[0], GAME[1], False), (300, 30)) is not None


def test_free_widgets_go_on_a_monitor_and_show_always_by_default():
    laptop = Monitor("eDP-1", False, 1920, 1080, 960, 1080)
    spec = WidgetSpec(components=("drive",), screen="eDP-1", x=10, y=20)
    assert place(spec, (None, (0, 0, 0, 0), False), (300, 30), [laptop]) == (970, 1100, 300, 30)


def test_load_widgets_reads_the_config_and_explains_mistakes(tmp_path):
    path = tmp_path / "config.toml"
    assert load_widgets(path) == []
    path.write_text(
        '[window]\nlayout = "compact"\n\n'
        '[[widgets]]\ncomponents = ["clearance", "drive"]\ndock = "game:top"\n\n'
        '[[widgets]]\ncomponents = "trade_here"\ndock = "game:right"\nwidth = 520\n'
    )
    first, second = load_widgets(path)
    assert first == WidgetSpec(components=("clearance", "drive"), dock="game:top")
    assert (second.components, second.width, second.shown) == (("trade_here",), 520, "with_game")
    for bad, message in (
        ('components = ["radar"]', "components must be one or more of"),
        ('components = "drive"\ndock = "game:middle"', "dock must be one of"),
        ('components = "drive"\nwidth = "wide"', "width must be a whole number"),
        ('components = "drive"\nfont_scale = 0', "font_scale must be a positive number"),
        ('components = "drive"\ncolour = "red"', "unknown settings: colour"),
    ):
        path.write_text(f"[[widgets]]\n{bad}\n")
        with pytest.raises(SystemExit, match=message):
            load_widgets(path)


def widget_from(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(f"[[widgets]]\n{text}\n")
    return load_widgets(path)[0]


def test_a_config_widget_can_be_a_preset(tmp_path):
    assert widget_from(tmp_path, 'widget = "top-strip"') == PRESETS["top-strip"].spec


def test_a_presets_id_is_its_name(tmp_path):
    assert widget_from(tmp_path, 'widget = "top-strip"').id == "top-strip"


def test_a_config_widget_can_change_a_presets_settings(tmp_path):
    spec = widget_from(tmp_path, 'widget = "top-strip"\ndock = "game:bottom"')
    assert (spec.components, spec.dock) == (("clearance", "drive"), "game:bottom")


def test_a_config_widget_can_give_a_preset_another_id(tmp_path):
    assert widget_from(tmp_path, 'widget = "top-strip"\nid = "strip2"').id == "strip2"


def test_a_preset_changed_badly_is_explained(tmp_path):
    with pytest.raises(SystemExit, match="dock must be one of"):
        widget_from(tmp_path, 'widget = "top-strip"\ndock = "game:middle"')


def test_an_unknown_preset_says_which_there_are(tmp_path):
    with pytest.raises(SystemExit, match="widget must be one of top-strip"):
        widget_from(tmp_path, 'widget = "radar"')


def test_a_presets_settings_are_checked_like_a_config_widgets(tmp_path):
    (tmp_path / "widget.toml").write_text('components = ["drive"]\ncolour = "red"\n')
    with pytest.raises(ValueError, match="unknown settings: colour"):
        read_preset(tmp_path)


def test_a_presets_state_must_name_a_state_for_each_component(tmp_path):
    (tmp_path / "widget.toml").write_text(
        'components = ["clearance", "drive"]\n[states]\nx = {drive = "docked"}\n'
    )
    with pytest.raises(ValueError, match="must name a state for each of clearance, drive"):
        read_preset(tmp_path)


def test_a_presets_state_must_name_states_its_components_have(tmp_path):
    (tmp_path / "widget.toml").write_text(
        'components = ["drive"]\n[states]\nx = {drive = "warp"}\n'
    )
    with pytest.raises(ValueError, match="drive has no state 'warp'"):
        read_preset(tmp_path)


def test_a_preset_cant_set_its_own_id(tmp_path):
    (tmp_path / "widget.toml").write_text('components = ["drive"]\nid = "x"\n')
    with pytest.raises(ValueError, match="id is its folder name"):
        read_preset(tmp_path)


def test_the_model_keeps_the_game_window_for_widgets():
    model = Model()
    seen = []
    model.subscribe("game_window", seen.append, initial=False)
    model.dispatch(
        {
            "type": "window/game",
            "geometry": [1282, 204, 1280, 720],
            "frame": [2, 2, 24, 2],
            "active": True,
        }
    )
    model.notify()
    assert seen == [GAME]


def test_hide_empty_must_be_a_boolean(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[[widgets]]\ncomponents = ["drive"]\nhide_empty = "no"\n')
    with pytest.raises(SystemExit, match="hide_empty must be true or false"):
        load_widgets(path)
    path.write_text('[[widgets]]\ncomponents = ["drive"]\nhide_empty = false\n')
    assert load_widgets(path)[0].hide_empty is False


def load_one(tmp_path, components):
    path = tmp_path / "config.toml"
    path.write_text(f"[[widgets]]\ncomponents = {components}\n")
    return load_widgets(path)[0]


def test_a_tab_group_is_a_tuple_among_the_components(tmp_path):
    spec = load_one(tmp_path, '["tip", {tabs = ["keys", "all_keys"]}, "status"]')
    assert spec.components == ("tip", ("keys", "all_keys"), "status")


def test_a_widgets_names_open_out_its_tab_groups(tmp_path):
    spec = load_one(tmp_path, '[{tabs = ["keys", "trade_table"]}, "status"]')
    assert spec.names == ("keys", "trade_table", "status")


@pytest.mark.parametrize(
    ("components", "message"),
    [
        ('[{tabs = ["keys"]}]', "a tab group is"),
        ('[{tabs = ["keys", "all_keys"], width = 3}]', "a tab group is"),
        ('[{tabs = ["keys", "drive"]}]', "drive can't be a tab; tabs can be keys, all_keys"),
        ('[{tabs = ["keys", "radar"]}]', "components must be one or more of"),
        ('["keys", {tabs = ["keys", "all_keys"]}]', "each component can be in a widget only once"),
    ],
)
def test_a_bad_tab_group_is_explained(tmp_path, components, message):
    with pytest.raises(SystemExit, match=message):
        load_one(tmp_path, components)
