"""Widgetwindows: a title bar over widgets stacked top to bottom, docked to the game (#124)."""

import pytest

from helper.layout import widgets_from_specs
from helper.widgets import (
    WindowSpec,
    load_widgets,
    load_widgetwindows,
    stacked,
    title_height,
    window_rect,
)

GAME = ((1282, 204, 1280, 720), (2, 2, 24, 2), True)  # geometry, frame, active
RIGHT = 1282 + 1280 + 2  # just past the game window's right border

TRADING = """
[[widgetwindows]]
id = "trading"
title = "Trading"
dock = "game:right"
width = 640
widgets = [
  { components = ["trade_here"], height = "*" },
  { components = ["hold"], height = 310 },
]
"""


def config(tmp_path, text=TRADING):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_a_widgetwindow_has_an_id_title_and_dock(tmp_path):
    (window,) = load_widgetwindows(config(tmp_path))
    assert (window.id, window.title, window.dock, window.width) == (
        "trading",
        "Trading",
        "game:right",
        640,
    )


def test_its_widgets_take_its_width_and_know_their_widgetwindow(tmp_path):
    widgets = widgets_from_specs(load_widgets(config(tmp_path)))
    assert {(w.spec.width, w.spec.window) for w in widgets} == {(640, "trading")}


def test_height_star_marks_the_widget_that_fills(tmp_path):
    specs = load_widgets(config(tmp_path))
    assert [(s.fill, s.height) for s in specs] == [(True, None), (False, 310)]


def test_beside_the_game_it_is_as_tall_as_the_game_window_and_its_title_bar():
    window = WindowSpec("w", "W", "game:right", width=640)
    assert window_rect(window, GAME) == (RIGHT, 204 - 24, 640, 24 + 720 + 2)


def test_on_the_left_it_ends_at_the_games_border():
    window = WindowSpec("w", "W", "game:left", width=300)
    assert window_rect(window, GAME)[0] == 1282 - 2 - 300


def test_above_the_game_it_is_as_wide_as_the_game_window_and_its_borders():
    window = WindowSpec("w", "W", "game:top", height=60)
    assert window_rect(window, GAME) == (1282 - 2, 204 - 24 - 60, 2 + 1280 + 2, 60)


def test_it_hides_while_the_game_isnt_active():
    window = WindowSpec("w", "W", "game:right", width=640)
    assert window_rect(window, (GAME[0], GAME[1], False)) is None


def test_shown_always_it_stays_while_the_game_isnt_active():
    window = WindowSpec("w", "W", "game:right", width=640, show="always")
    assert window_rect(window, (GAME[0], GAME[1], False)) is not None


def test_widgets_stack_under_the_title_and_the_filler_takes_the_rest():
    rects = stacked((0, 0, 640, 720), 24, [("trade", 50, True), ("hold", 310, False)])
    assert rects == {"trade": (0, 24, 640, 386), "hold": (0, 410, 640, 310)}


def test_without_a_filler_the_last_shown_widget_fills():
    rects = stacked((0, 0, 640, 720), 24, [("trade", 100, False), ("hold", 310, False)])
    assert rects["hold"] == (0, 124, 640, 596)


def test_a_hidden_widget_leaves_no_gap():
    rects = stacked((0, 0, 640, 720), 24, [("trade", None, False), ("hold", 310, True)])
    assert rects == {"trade": None, "hold": (0, 24, 640, 696)}


def test_with_the_filler_hidden_the_last_shown_widget_fills():
    rects = stacked((0, 0, 640, 720), 24, [("hold", 310, False), ("trade", None, True)])
    assert rects["hold"] == (0, 24, 640, 696)


def test_the_title_bar_follows_the_layouts_text_size():
    big = WindowSpec("w", "W", "game:right", width=640, layout="large")
    assert title_height(big) > title_height(WindowSpec("w", "W", "game:right", width=640))


def test_a_named_widget_in_a_widgetwindow_keeps_its_name_as_its_id(tmp_path):
    named = TRADING.replace('components = ["hold"]', 'widget = "hold-beside"')
    widgets = widgets_from_specs(load_widgets(config(tmp_path, named)))
    assert widgets[1].id == "hold-beside"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("height = 310", "height = 310, y = 10"), "widgetwindow places it, so it can't set y"),
        (("height = 310", "height = 310, width = 10"), "can't set width"),
        (("width = 640\n", ""), "width must be a whole number of pixels"),
        (("width = 640", "width = 640\nheight = 300"), "its other size is the game's"),
        (('dock = "game:right"', 'dock = "game:middle"'), "dock must be one of"),
        (('title = "Trading"\n', ""), "title must be some text"),
        (('id = "trading"\n', ""), "id must be letters"),
        (("height = 310", 'height = "*"'), 'only one widget can have height = "\\*"'),
        (("width = 640", "width = 640\nscreen = 1"), "unknown settings: screen"),
    ],
)
def test_a_widgetwindow_set_up_badly_is_explained(tmp_path, change, message):
    with pytest.raises(SystemExit, match=message):
        load_widgets(config(tmp_path, TRADING.replace(*change)))


def test_two_widgetwindows_cant_share_an_id(tmp_path):
    with pytest.raises(SystemExit, match="two widgetwindows have the id 'trading'"):
        load_widgets(config(tmp_path, TRADING + TRADING.replace("trade_here", "drive")))


def test_the_old_docks_table_says_what_replaced_it(tmp_path):
    with pytest.raises(SystemExit, match=r"\[\[docks\]\] is now \[\[widgetwindows\]\]"):
        load_widgets(config(tmp_path, '[[docks]]\ndock = "game:right"\n'))


def test_a_config_widget_cant_say_which_widgetwindow_its_in(tmp_path):
    path = config(tmp_path, '[[widgets]]\ncomponents = ["drive"]\nwindow = "trading"\n')
    with pytest.raises(SystemExit, match="unknown settings: window"):
        load_widgets(path)
