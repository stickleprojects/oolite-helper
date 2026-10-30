"""Docks that stack their widgets beside the game window (#80)."""

from dataclasses import replace

import pytest

from helper.layout import widgets_from_specs
from helper.widgets import along, load_widgets, place, stack_offset

GAME = ((1282, 204, 1280, 720), (2, 2, 24, 2), True)  # geometry, frame, active
RIGHT = 1282 + 1280 + 2  # just past the game window's right border

RIGHT_DOCK = """
[[docks]]
dock = "game:right"
width = 640
widgets = [
  { components = ["trade_here"], height = 400 },
  { components = ["hold"], height = 310 },
]
"""


def docked(tmp_path, text=RIGHT_DOCK):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return widgets_from_specs(load_widgets(path))


def rects(widgets, sizes=None, closed=()):
    sizes = sizes or {}

    def size_along(widget):
        return None if widget.id in closed else along(widget.spec, sizes.get(widget.id, (0, 0)))

    return [
        place(w.spec, GAME, sizes.get(w.id, (0, 0)), (), stack_offset(widgets, w.id, size_along))
        for w in widgets
        if w.id not in closed
    ]


def test_a_right_dock_stacks_its_widgets_down_from_the_top_of_the_game(tmp_path):
    assert rects(docked(tmp_path)) == [(RIGHT, 204, 640, 400), (RIGHT, 604, 640, 310)]


def test_every_widget_in_a_dock_takes_its_width(tmp_path):
    assert {w.spec.width for w in docked(tmp_path)} == {640}


def test_a_gap_goes_between_the_widgets(tmp_path):
    widgets = docked(tmp_path, RIGHT_DOCK.replace("width = 640", "width = 640\ngap = 8"))
    assert rects(widgets)[1][1] == 204 + 400 + 8


def test_a_closed_widget_leaves_no_gap(tmp_path):
    widgets = docked(tmp_path)
    assert rects(widgets, closed={widgets[0].id}) == [(RIGHT, 204, 640, 310)]


def test_a_widget_with_no_height_is_as_tall_as_its_components_ask(tmp_path):
    widgets = docked(tmp_path, RIGHT_DOCK.replace(", height = 400", ""))
    first = widgets[0].id
    assert rects(widgets, sizes={first: (500, 250)}) == [
        (RIGHT, 204, 640, 250),
        (RIGHT, 454, 640, 310),
    ]


def test_a_top_dock_stacks_left_to_right_at_its_height(tmp_path):
    widgets = docked(
        tmp_path,
        """
[[docks]]
dock = "game:top"
height = 30
widgets = [{ components = ["clearance"], width = 300 }, { components = ["drive"], width = 200 }]
""",
    )
    above = 204 - 24 - 30
    assert rects(widgets) == [(1282, above, 300, 30), (1582, above, 200, 30)]


def test_widgets_in_other_docks_dont_move_each_other(tmp_path):
    widgets = docked(tmp_path)
    free = replace(widgets[0], id="free", spec=replace(widgets[0].spec, stack=None))
    assert stack_offset((free, *widgets), widgets[0].id, lambda w: 999) == 0


def test_a_named_widget_in_a_dock_keeps_its_name_as_its_id(tmp_path):
    named = RIGHT_DOCK.replace('components = ["hold"]', 'widget = "hold-beside"')
    widgets = docked(tmp_path, named)
    assert widgets[1].id == "hold-beside"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("height = 400", "height = 400, y = 10"), "the dock places it, so it can't set y"),
        (("height = 400", "height = 400, width = 10"), "can't set width"),
        (("width = 640\n", ""), "width must be a whole number of pixels"),
        (('dock = "game:right"', 'dock = "game:middle"'), "dock must be one of"),
        (("width = 640", "width = 640\nscreen = 1"), "unknown settings: screen"),
    ],
)
def test_a_dock_set_up_badly_is_explained(tmp_path, change, message):
    with pytest.raises(SystemExit, match=message):
        docked(tmp_path, RIGHT_DOCK.replace(*change))


def test_a_side_can_have_only_one_dock(tmp_path):
    with pytest.raises(SystemExit, match="game:right already has a"):
        docked(tmp_path, RIGHT_DOCK + RIGHT_DOCK)


def test_a_config_widget_cant_say_which_dock_stack_its_in(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[[widgets]]\ncomponents = ["drive"]\nstack = 1\n')
    with pytest.raises(SystemExit, match="unknown settings: stack"):
        load_widgets(path)
