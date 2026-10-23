import pytest

from helper.model import Model
from helper.screen import Monitor
from helper.widgets import WidgetSpec, load_widgets, place

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
