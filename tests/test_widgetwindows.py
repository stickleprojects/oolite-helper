"""Widgetwindows: a title bar over widgets stacked top to bottom, docked to the game (#124)."""

import pytest

from helper.layout import widgets_from_specs
from helper.screen import Monitor
from helper.settings import WindowSpec
from helper.widgets import (
    MIN_SIZE,
    dropped,
    landing,
    move_to,
    places,
    resize_edges,
    resized,
    stacked,
    title_height,
    window_rect,
)
from tests.configs import load_widgets, load_widgetwindows

GAME = ((1282, 204, 1280, 720), (2, 2, 24, 2), True)  # geometry, frame, active
NO_GAME = (None, (0, 0, 0, 0), False)
LAPTOP = Monitor("eDP-1", False, 1920, 1080, 960, 1080)
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
    window = WindowSpec(id="w", title="W", dock="game:right", width=640)
    assert window_rect(window, GAME) == (RIGHT, 204 - 24, 640, 24 + 720 + 2)


def test_on_the_left_it_ends_at_the_games_border():
    window = WindowSpec(id="w", title="W", dock="game:left", width=300)
    assert window_rect(window, GAME)[0] == 1282 - 2 - 300


def test_above_the_game_it_is_as_wide_as_the_game_window_and_its_borders():
    window = WindowSpec(id="w", title="W", dock="game:top", height=60)
    assert window_rect(window, GAME) == (1282 - 2, 204 - 24 - 60, 2 + 1280 + 2, 60)


def test_it_hides_while_the_game_isnt_active():
    window = WindowSpec(id="w", title="W", dock="game:right", width=640)
    assert window_rect(window, (GAME[0], GAME[1], False)) is None


def test_shown_always_it_stays_while_the_game_isnt_active():
    window = WindowSpec(id="w", title="W", dock="game:right", width=640, show="always")
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
    big = WindowSpec(id="w", title="W", dock="game:right", width=640, layout="large")
    assert title_height(big) > title_height(
        WindowSpec(id="w", title="W", dock="game:right", width=640)
    )


def test_a_named_widget_in_a_widgetwindow_keeps_its_name_as_its_id(tmp_path):
    named = TRADING.replace('components = ["hold"]', 'widget = "hold-beside"')
    widgets = widgets_from_specs(load_widgets(config(tmp_path, named)))
    assert widgets[1].id == "hold-beside"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("height = 310", "height = 310, y = 10"), "widgetwindow places it: can't set y"),
        (("height = 310", "height = 310, width = 10"), "can't set width"),
        (("width = 640\n", ""), "width must be a whole number of pixels"),
        (("width = 640", "width = 640\nheight = 300"), "its other size is the game's"),
        (('dock = "game:right"', 'dock = "game:middle"'), "dock must be one of"),
        (('title = "Trading"\n', ""), "title is missing"),
        (('id = "trading"\n', ""), "widgetwindow 1: id is missing$"),
        (("height = 310", 'height = "*"'), 'only one widget can have height = "\\*"'),
        (("width = 640", "width = 640\ngap = 1"), "unknown setting gap"),
        (("width = 640", 'width = 640\nscreen = "eDP-1"'), "docked, it can't set screen"),
        (('dock = "game:right"', 'dock = "screen:eDP-1:middle"'), "dock must be one of"),
        (('dock = "game:right"\n', ""), "floating, it needs a screen"),
    ],
)
def test_a_widgetwindow_set_up_badly_is_explained(tmp_path, change, message):
    with pytest.raises(SystemExit, match=message):
        load_widgets(config(tmp_path, TRADING.replace(*change)))


def test_two_widgetwindows_cant_share_an_id(tmp_path):
    with pytest.raises(SystemExit, match="two widgetwindows have the id 'trading'"):
        load_widgets(config(tmp_path, TRADING + TRADING.replace("trade_here", "drive")))


def test_a_config_widget_cant_say_which_widgetwindow_its_in(tmp_path):
    path = config(tmp_path, '[[widgets]]\ncomponents = ["drive"]\nwindow = "trading"\n')
    with pytest.raises(SystemExit, match="unknown setting window"):
        load_widgets(path)


def test_on_a_monitors_right_edge_it_is_the_monitors_height():
    window = WindowSpec(id="w", title="W", dock="screen:eDP-1:right", width=600)
    assert window_rect(window, NO_GAME, [LAPTOP]) == (960 + 1920 - 600, 1080, 600, 1080)


def test_on_a_monitors_bottom_edge_it_is_the_monitors_width():
    window = WindowSpec(id="w", title="W", dock="screen:eDP-1:bottom", height="25%")
    assert window_rect(window, NO_GAME, [LAPTOP]) == (960, 1080 + 810, 1920, 270)


def test_floating_at_100_percent_it_fills_its_monitor():
    window = WindowSpec(id="w", title="W", screen="eDP-1", width="100%", height="100%")
    assert window_rect(window, NO_GAME, [LAPTOP]) == (960, 1080, 1920, 1080)


def test_floating_it_sits_at_its_place_on_the_monitor():
    window = WindowSpec(id="w", title="W", screen="eDP-1", x=10, y=20, width=500, height=400)
    assert window_rect(window, NO_GAME, [LAPTOP]) == (970, 1100, 500, 400)


def test_off_the_game_it_shows_whether_or_not_the_game_is_active():
    window = WindowSpec(id="w", title="W", dock="screen:eDP-1:left", width=600)
    assert window_rect(window, NO_GAME, [LAPTOP]) is not None


def test_on_a_monitor_that_isnt_there_it_hides():
    window = WindowSpec(id="w", title="W", screen="HDMI-9", width=500, height=400)
    assert window_rect(window, NO_GAME, [LAPTOP]) is None


def test_off_the_game_its_text_is_compact_too():
    window = WindowSpec(id="w", title="W", screen="eDP-1", width=500, height=400)
    assert title_height(window) == title_height(
        WindowSpec(id="w", title="W", dock="game:right", width=640)
    )


FLOATING = """
[[widgetwindows]]
id = "laptop"
title = "Laptop"
screen = "eDP-1"
width = "100%"
height = "100%"
widgets = [{ components = ["trade_here"] }]
"""


def test_a_floating_widgetwindow_reads_its_screen_and_sizes(tmp_path):
    (window,) = load_widgetwindows(config(tmp_path, FLOATING))
    assert (window.dock, window.screen, window.width, window.height) == (
        None,
        "eDP-1",
        "100%",
        "100%",
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('width = "100%"', 'width = "big"'), "width must be pixels or a percentage"),
        (('screen = "eDP-1"\n', ""), "floating, it needs a screen"),
        (('screen = "eDP-1"', 'screen = "eDP-1"\nx = 1.5'), "x must be a whole number"),
    ],
)
def test_a_floating_widgetwindow_set_up_badly_is_explained(tmp_path, change, message):
    with pytest.raises(SystemExit, match=message):
        load_widgets(config(tmp_path, FLOATING.replace(*change)))


def test_on_a_monitors_right_edge_its_inner_edge_resizes_it():
    assert resize_edges(WindowSpec(id="w", title="W", dock="screen:eDP-1:right", width=600)) == (
        "left",
    )


def test_floating_every_edge_resizes_it():
    window = WindowSpec(id="w", title="W", screen="eDP-1", width=500, height=400)
    assert resize_edges(window) == ("left", "right", "top", "bottom")


def test_a_resized_floating_widgetwindow_moves_and_resizes_on_its_monitor():
    window = WindowSpec(id="w", title="W", screen="eDP-1", width=500, height=400)
    assert resized(window, (1000, 1100, 600, 300), [LAPTOP]) == [
        {"type": "layout/move_widget", "id": "w", "x": 40, "y": 20},
        {"type": "layout/resize_widget", "id": "w", "width": 600, "height": 300},
    ]


def test_a_resized_widgetwindow_beside_the_game_changes_only_its_width():
    window = WindowSpec(id="w", title="W", dock="game:right", width=640)
    assert resized(window, (0, 0, 700, 999), []) == [
        {"type": "layout/resize_widget", "id": "w", "width": 700}
    ]


def test_a_widgetwindow_cant_be_resized_too_small():
    window = WindowSpec(id="w", title="W", dock="game:top", height=60)
    assert resized(window, (0, 0, 999, 5), [])[0]["height"] == MIN_SIZE


ON_GAME_RIGHT = WindowSpec(id="w", title="W", dock="game:right", width=640)
OUTER = (1282 - 2, 204 - 24, 2 + 1280 + 2, 24 + 720 + 2)  # the game window, frame included
MAIN = Monitor("DP-2", True, 3840, 1080, 0, 0)
SCREENS = [MAIN, LAPTOP]
ANYWHERE = (1200, 300, 640, 746)  # the dragged window; the pointer decides


def drop(pointer, window=ON_GAME_RIGHT):
    return dropped(window, ANYWHERE, GAME, SCREENS, pointer)


def test_dropped_with_the_pointer_just_right_of_the_game_it_docks_there():
    move = drop((OUTER[0] + OUTER[2] + 20, 400))
    assert (move["dock"], move["width"], move["height"]) == ("game:right", 640, None)


def test_dropped_with_the_pointer_just_left_of_the_game_it_docks_on_the_left():
    assert drop((OUTER[0] - 20, 400))["dock"] == "game:left"


def test_dropped_with_the_pointer_just_above_the_game_it_docks_on_top():
    assert drop((1900, OUTER[1] - 20))["dock"] == "game:top"


def test_turning_from_a_side_to_the_top_it_takes_a_third_of_the_edge():
    move = drop((1900, OUTER[1] - 20))
    assert (move["width"], move["height"]) == (None, OUTER[3] // 3)


def test_dropped_with_the_pointer_by_a_monitors_edge_it_docks_to_that_edge():
    assert drop((960 + 1920 - 10, 1500))["dock"] == "screen:eDP-1:right"


def test_dropped_with_the_pointer_by_a_monitors_bottom_it_docks_there():
    assert drop((1500, 1080 + 1080 - 10))["dock"] == "screen:eDP-1:bottom"


def test_dropped_away_from_edges_it_floats_on_the_screen_under_the_pointer():
    move = dropped(ON_GAME_RIGHT, (1200, 1300, 600, 500), GAME, SCREENS, (1500, 1500))
    assert move == {
        "type": "layout/move_widget",
        "id": "w",
        "dock": None,
        "screen": "eDP-1",
        "x": 240,
        "y": 220,
        "width": 600,
        "height": 500,
    }


def test_floating_it_is_kept_on_its_screen():
    move = dropped(ON_GAME_RIGHT, (2700, 1300, 600, 500), GAME, SCREENS, (2800, 1500))
    assert move["x"] == 1920 - 600


def test_dropped_on_no_monitor_it_stays_put():
    assert dropped(ON_GAME_RIGHT, (9000, 9000, 600, 500), NO_GAME, [LAPTOP], (9100, 9100)) is None


def test_its_ghost_shows_the_whole_edge_it_would_dock_to():
    ghost = landing(ON_GAME_RIGHT, ANYWHERE, GAME, SCREENS, (960 + 5, 1500))
    assert ghost == (960, 1080, 640, 1080)


def test_its_anchor_list_offers_the_games_edges_each_screens_and_float():
    labels = [label for _, label in places([LAPTOP], GAME)]
    assert labels == [
        "Game: left",
        "Game: right",
        "Game: top",
        "Game: bottom",
        "eDP-1: left",
        "eDP-1: right",
        "eDP-1: top",
        "eDP-1: bottom",
        "Float",
    ]


def test_without_a_game_window_its_list_has_no_game_edges():
    assert [place for place, _ in places([LAPTOP], NO_GAME)][0] == "screen:eDP-1:left"


def test_sent_from_its_list_to_a_screen_edge_it_keeps_its_width():
    move = move_to(ON_GAME_RIGHT, "screen:eDP-1:left", ANYWHERE, GAME, SCREENS)
    assert (move["dock"], move["width"]) == ("screen:eDP-1:left", 640)


def test_floated_off_a_side_dock_it_is_half_the_screens_height():
    move = move_to(ON_GAME_RIGHT, "float", (1200, 1080, 640, 1080), GAME, SCREENS)
    assert (move["width"], move["height"]) == (640, 540)


def test_its_text_size_stays_the_same_wherever_it_is_moved(tmp_path):
    (window,) = load_widgetwindows(config(tmp_path))
    floating = window.changed(dock=None, screen="eDP-1", width=500, height=400)
    assert floating.layout == window.layout == "compact"
