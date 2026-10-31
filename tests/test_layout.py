import pytest

from helper import layout
from helper.layout import (
    LayoutFile,
    Widget,
    differences,
    reduce_layout,
    widgets_from_specs,
    windows_from_specs,
)
from helper.model import Model
from helper.widgets import WidgetSpec, WindowSpec, load_widgets

SPECS = [
    WidgetSpec(components=("drive",), dock="game:top"),
    WidgetSpec(components=("trade_here",), dock="game:right", width=520, id="trade"),
]


def test_panels_get_stable_ids_from_the_config():
    drive, trade = widgets_from_specs(SPECS)
    assert (drive.id, trade.id) == ("widget1:drive", "trade")
    assert drive.open and drive.spec is SPECS[0]


def test_ids_must_be_unique():
    with pytest.raises(SystemExit, match="two widgets have the id 'trade'"):
        widgets_from_specs([SPECS[1], SPECS[1]])


def test_the_id_setting_is_checked(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[[widgets]]\ncomponents = ["drive"]\nid = "has space"\n')
    with pytest.raises(SystemExit, match="id must be letters"):
        load_widgets(path)
    path.write_text('[[widgets]]\ncomponents = ["drive"]\nid = "top-strip"\n')
    assert load_widgets(path)[0].id == "top-strip"


def test_layout_actions_change_only_their_widget():
    widgets = widgets_from_specs(SPECS)
    moved = reduce_layout(widgets, {"type": "layout/move_widget", "id": "trade", "x": 4, "y": 9})
    assert moved[0] is widgets[0]
    assert (moved[1].spec.x, moved[1].spec.y, moved[1].spec.width) == (4, 9, 520)
    sized = reduce_layout(
        moved, {"type": "layout/resize_widget", "id": "trade", "width": 300, "height": 200}
    )
    assert (sized[1].spec.width, sized[1].spec.height, sized[1].spec.x) == (300, 200, 4)
    closed = reduce_layout(sized, {"type": "layout/close_widget", "id": "trade"})
    assert not closed[1].open
    assert reduce_layout(closed, {"type": "layout/open_widget", "id": "trade"})[1].open


def test_bad_layout_actions_fail():
    widgets = widgets_from_specs(SPECS)
    with pytest.raises(ValueError, match="no widget 'nope'"):
        reduce_layout(widgets, {"type": "layout/close_widget", "id": "nope"})
    with pytest.raises(ValueError, match="unknown layout action"):
        reduce_layout(widgets, {"type": "layout/fly", "id": "trade"})


def test_the_model_has_a_layout_topic():
    model = Model(layout=widgets_from_specs(SPECS))
    seen = []
    model.subscribe("layout", seen.append, initial=False)
    model.dispatch({"type": "layout/close_widget", "id": "trade"})
    model.notify()
    assert len(seen) == 1 and not seen[0][1].open


def test_changes_are_saved_as_differences_and_loaded_back(tmp_path):
    path = tmp_path / "layout.toml"
    defaults = widgets_from_specs(SPECS)
    widgets = reduce_layout(defaults, {"type": "layout/move_widget", "id": "trade", "x": 4, "y": 0})
    widgets = reduce_layout(widgets, {"type": "layout/close_widget", "id": "widget1:drive"})
    assert differences(defaults, widgets) == {"widget1:drive": {"open": False}, "trade": {"x": 4}}
    LayoutFile(defaults, path).save(widgets)
    assert '[widgets."trade"]\nx = 4\n' in path.read_text()
    assert layout.load(defaults, path) == widgets
    LayoutFile(defaults, path).save(defaults)  # back to config.toml: no file needed
    assert not path.exists()


def test_a_bad_layout_file_is_skipped_not_fatal(tmp_path, capsys):
    path = tmp_path / "layout.toml"
    defaults = widgets_from_specs(SPECS)
    path.write_text("this isn't toml")
    assert layout.load(defaults, path) == defaults
    assert "ignoring" in capsys.readouterr().err
    path.write_text(
        '[widgets.trade]\nx = "far"\nwidth = -1\ny = 7\nopen = false\n[widgets.gone]\nx=1\n'
    )
    trade = layout.load(defaults, path)[1]
    assert trade == Widget("trade", WidgetSpec(**{**vars(SPECS[1]), "y": 7}), open=False)


TRADING = WindowSpec("trading", "Trading", "game:right", width=640)


def test_a_resize_can_change_just_the_width():
    windows = windows_from_specs([TRADING])
    resized = reduce_layout(
        windows, {"type": "layout/resize_widget", "id": "trading", "width": 700}
    )
    assert (resized[0].spec.width, resized[0].spec.height) == (700, None)


def test_layout_actions_with_a_widgetwindows_id_change_the_windows_topic():
    model = Model(layout=widgets_from_specs(SPECS), windows=windows_from_specs([TRADING]))
    model.dispatch({"type": "layout/resize_widget", "id": "trading", "width": 700})
    assert model.topic("windows")[0].spec.width == 700


def test_a_widgetwindow_cant_share_a_widgets_id():
    with pytest.raises(SystemExit, match="a widget and a widgetwindow have the id 'trade'"):
        windows_from_specs(
            [WindowSpec("trade", "T", "game:right", width=1)], widgets_from_specs(SPECS)
        )


def test_a_widgetwindows_new_size_is_saved_and_loaded_back(tmp_path):
    path = tmp_path / "layout.toml"
    widgets, windows = widgets_from_specs(SPECS), windows_from_specs([TRADING])
    wider = reduce_layout(windows, {"type": "layout/resize_widget", "id": "trading", "width": 700})
    LayoutFile(widgets, path, windows, widgets, windows).save_windows(wider)
    assert layout.load(windows, path) == wider


def test_saving_widgets_keeps_the_widgetwindows_changes(tmp_path):
    path = tmp_path / "layout.toml"
    widgets, windows = widgets_from_specs(SPECS), windows_from_specs([TRADING])
    wider = reduce_layout(windows, {"type": "layout/resize_widget", "id": "trading", "width": 700})
    saver = LayoutFile(widgets, path, windows, widgets, wider)
    saver.save(reduce_layout(widgets, {"type": "layout/close_widget", "id": "trade"}))
    assert layout.load(windows, path) == wider
