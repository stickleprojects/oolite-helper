"""The radar's colours follow ShipEntity scannerDisplayColorForShip (1.92.1)."""

import pytest

from helper import radar

RED, YELLOW, GREEN = "#ff4000", "#ffff00", "#00ff00"


def shown(**blip):
    colour, flash = radar.colours(blip, blip.pop("has_filter", False))
    return radar.css(colour), radar.css(flash)


@pytest.mark.parametrize(
    ("scan_class", "expected"),
    [
        ("CLASS_CARGO", ("#e6e6e6", None)),
        ("CLASS_ROCK", ("#e6e6e6", None)),
        ("CLASS_THARGOID", (GREEN, RED)),
        ("CLASS_MISSILE", ("#00ffff", None)),
        ("CLASS_STATION", (GREEN, None)),
        ("CLASS_BUOY", (YELLOW, GREEN)),
        ("CLASS_POLICE", ("#8000ff", None)),
        ("CLASS_MILITARY", ("#8000ff", None)),
        ("CLASS_MINE", (RED, YELLOW)),
        ("CLASS_NEUTRAL", (YELLOW, None)),
    ],
)
def test_each_scan_class_has_the_scanners_colours(scan_class, expected):
    assert shown(scanClass=scan_class) == expected


def test_a_hostile_ship_is_red_orange():
    assert shown(scanClass="CLASS_NEUTRAL", hostile=True) == (RED, None)


def test_hostile_police_flash_purple_red():
    assert shown(scanClass="CLASS_POLICE", hostile=True) == ("#8000ff", "#ff0080")


def test_two_scripted_colours_flash_the_first_in_the_flash_phase():
    blip = {"scanClass": "CLASS_NEUTRAL", "colours": [[1, 0, 0, 1], [0, 0, 1, 1], None, None]}
    assert shown(**blip) == ("#0000ff", "#ff0000")


def test_one_scripted_colour_is_shown_steady():
    blip = {"scanClass": "CLASS_POLICE", "colours": [None, [0, 0, 1, 1], None, None]}
    assert shown(**blip) == ("#0000ff", None)


def test_scripted_hostile_colours_win_when_hostile():
    blip = {"hostile": True, "colours": [[1, 0, 0, 1], None, [0, 1, 0, 1], None]}
    assert shown(**blip) == (GREEN, None)


def test_scripted_hostile_colours_are_ignored_when_not_hostile():
    blip = {"hostile": False, "colours": [[1, 0, 0, 1], None, [0, 1, 0, 1], None]}
    assert shown(**blip) == ("#ff0000", None)


def test_a_jamming_ship_is_drawn_clear_without_a_filter():
    assert radar.colours({"jamming": True}) is None


def test_a_jamming_ship_flashes_grey_and_purple_with_a_filter():
    assert shown(jamming=True, has_filter=True) == ("#661a66", "#4c4c4c")


def test_a_hostile_jamming_ship_flashes_grey_and_red_with_a_filter():
    assert shown(jamming=True, hostile=True, has_filter=True) == (RED, "#4c4c4c")


def test_doing_says_who_a_ship_attacks():
    assert radar.doing({"attacking": True, "target": "you"}) == "attacking you"


def test_doing_joins_attacking_and_fleeing():
    assert radar.doing({"attacking": True, "target": "you", "fleeing": True}) == (
        "attacking you, fleeing"
    )


def test_doing_is_none_for_a_ship_doing_nothing():
    assert radar.doing({"attacking": False, "target": "you"}) is None


def test_blips_are_nearest_first_in_km():
    message = {"blips": [{"name": "B", "distance": 9050}, {"name": "A", "distance": 1210}]}
    assert [(b["name"], b["distance_km"]) for b in radar.blips(message)] == [("A", 1.2), ("B", 9.1)]


def test_blips_leave_out_jamming_ships_without_a_filter():
    message = {"filter": False, "blips": [{"name": "Ghost", "jamming": True, "distance": 100}]}
    assert radar.blips(message) == ()


def test_no_message_is_no_blips():
    assert radar.blips(None) == ()
