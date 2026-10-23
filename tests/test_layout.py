import pytest

from helper import layout
from helper.layout import LayoutFile, Panel, differences, panels_from_specs, reduce_layout
from helper.model import Model
from helper.widgets import WidgetSpec, load_widgets

SPECS = [
    WidgetSpec(views=("drive",), dock="game:top"),
    WidgetSpec(views=("trade_here",), dock="game:right", width=520, id="trade"),
]


def test_panels_get_stable_ids_from_the_config():
    drive, trade = panels_from_specs(SPECS)
    assert (drive.id, trade.id) == ("widget1:drive", "trade")
    assert drive.open and drive.spec is SPECS[0]


def test_ids_must_be_unique():
    with pytest.raises(SystemExit, match="two widgets have the id 'trade'"):
        panels_from_specs([SPECS[1], SPECS[1]])


def test_the_id_setting_is_checked(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[[widgets]]\nviews = ["drive"]\nid = "has space"\n')
    with pytest.raises(SystemExit, match="id must be letters"):
        load_widgets(path)
    path.write_text('[[widgets]]\nviews = ["drive"]\nid = "top-strip"\n')
    assert load_widgets(path)[0].id == "top-strip"


def test_layout_actions_change_only_their_panel():
    panels = panels_from_specs(SPECS)
    moved = reduce_layout(panels, {"type": "layout/move_panel", "id": "trade", "x": 4, "y": 9})
    assert moved[0] is panels[0]
    assert (moved[1].spec.x, moved[1].spec.y, moved[1].spec.width) == (4, 9, 520)
    sized = reduce_layout(
        moved, {"type": "layout/resize_panel", "id": "trade", "width": 300, "height": 200}
    )
    assert (sized[1].spec.width, sized[1].spec.height, sized[1].spec.x) == (300, 200, 4)
    closed = reduce_layout(sized, {"type": "layout/close_panel", "id": "trade"})
    assert not closed[1].open
    assert reduce_layout(closed, {"type": "layout/open_panel", "id": "trade"})[1].open


def test_bad_layout_actions_fail():
    panels = panels_from_specs(SPECS)
    with pytest.raises(ValueError, match="no panel 'nope'"):
        reduce_layout(panels, {"type": "layout/close_panel", "id": "nope"})
    with pytest.raises(ValueError, match="unknown layout action"):
        reduce_layout(panels, {"type": "layout/fly", "id": "trade"})


def test_the_model_has_a_layout_topic():
    model = Model(layout=panels_from_specs(SPECS))
    seen = []
    model.subscribe("layout", seen.append, initial=False)
    model.dispatch({"type": "layout/close_panel", "id": "trade"})
    model.notify()
    assert len(seen) == 1 and not seen[0][1].open


def test_changes_are_saved_as_differences_and_loaded_back(tmp_path):
    path = tmp_path / "layout.toml"
    defaults = panels_from_specs(SPECS)
    panels = reduce_layout(defaults, {"type": "layout/move_panel", "id": "trade", "x": 4, "y": 0})
    panels = reduce_layout(panels, {"type": "layout/close_panel", "id": "widget1:drive"})
    assert differences(defaults, panels) == {"widget1:drive": {"open": False}, "trade": {"x": 4}}
    LayoutFile(defaults, path).save(panels)
    assert '[panels."trade"]\nx = 4\n' in path.read_text()
    assert layout.load(defaults, path) == panels
    LayoutFile(defaults, path).save(defaults)  # back to config.toml: no file needed
    assert not path.exists()


def test_a_bad_layout_file_is_skipped_not_fatal(tmp_path, capsys):
    path = tmp_path / "layout.toml"
    defaults = panels_from_specs(SPECS)
    path.write_text("this isn't toml")
    assert layout.load(defaults, path) == defaults
    assert "ignoring" in capsys.readouterr().err
    path.write_text(
        '[panels.trade]\nx = "far"\nwidth = -1\ny = 7\nopen = false\n[panels.gone]\nx=1\n'
    )
    trade = layout.load(defaults, path)[1]
    assert trade == Panel("trade", WidgetSpec(**{**vars(SPECS[1]), "y": 7}), open=False)
