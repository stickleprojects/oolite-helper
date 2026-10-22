from pathlib import Path

from helper import contexts, plist
from helper.keys import Keymap
from helper.state import GameState

FIXTURE = Path(__file__).parent / "fixtures" / "keyconfig2.plist"


def fixture_keymap():
    data = plist.load(FIXTURE)
    return Keymap(data["default"], {})


def test_every_action_name_is_in_real_keyconfig_fixture():
    keyconfig = plist.load(FIXTURE)
    actions = {
        action
        for value in vars(contexts).values()
        if isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], list)
        for action in value[1]
    }
    actions.update(
        action
        for groups in contexts.SCREEN_SECTIONS.values()
        for _, section_actions in groups
        for action in section_actions
    )
    assert actions <= keyconfig["default"].keys()


def test_tips_use_real_keys_and_unbound_actions_are_clear():
    keymap = fixture_keymap()
    state = GameState()
    state.apply({"type": "ready", "docked": False, "alert": 1})
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    assert contexts.tip(state, keymap) == "Press H again to cancel the countdown."

    state.apply({"type": "countdown_end"})
    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "requiresClearance": True,
            "clearance": "DOCKING_CLEARANCE_STATUS_NONE",
        }
    )
    assert contexts.tip(state, keymap) == (
        "Shift+L asks your current target, so target the station first "
        "(R with it ahead, or + / Num +)."
    )
    keymap.bindings.pop("key_hyperspace")
    state.apply({"type": "aegis", "inside": False})
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    assert "(unbound)" in contexts.tip(state, keymap)


def test_context_sections_select_screen_and_context_actions():
    state = GameState()
    state.apply({"type": "ready", "docked": False})
    state.apply({"type": "gui", "to": "GUI_SCREEN_MARKET"})
    assert contexts.sections(state) == [contexts.MARKET, contexts.FLIGHT_SCREENS]

    state.apply({"type": "gui", "to": "GUI_SCREEN_MAIN"})
    state.apply({"type": "alert", "level": 3})
    assert contexts.sections(state)[0] == contexts.COMBAT


def test_all_key_groups_list_each_action_once_and_cover_every_context_section():
    grouped = [action for _, actions in contexts.ALL_KEY_GROUPS for action in actions]
    # keyFunctionList in 1.92.1 lists 117 actions in 14 groups (checked against the
    # full keyconfig2.plist; the fixture is trimmed).
    assert len(contexts.ALL_KEY_GROUPS) == 14
    assert len(grouped) == len(set(grouped)) == 117
    sectioned = {
        action
        for value in vars(contexts).values()
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], list)
        for action in value[1]
    }
    assert sectioned <= set(grouped)


def test_weapons_shown_when_flying_or_near_a_station_without_red_alert():
    state = GameState()
    state.apply({"type": "ready", "docked": False, "alert": 1})
    assert contexts.WEAPONS in contexts.sections(state)
    state.apply({"type": "aegis", "inside": True, "station": "Lave Station"})
    assert state.context == "near station"
    assert contexts.WEAPONS in contexts.sections(state)


def test_a_nearby_mass_warns_before_and_during_a_jump():
    from helper.contexts import tip
    from helper.state import GameState

    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 1})
    state.apply({"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747})
    assert tip(state, None) == (
        "You can't jump yet: Coriolis Station is too close. Fly more than 6.7 km away from it."
    )
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    assert tip(state, None).startswith("This jump will fail")
    state.apply({"type": "jump_blocker", "by": None, "clearAt": None})
    assert tip(state, None) == ""


def test_mass_lock_says_what_holds_the_torus_drive():
    from helper.contexts import tip
    from helper.state import GameState

    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 2})
    state.apply({"type": "mass_lock", "by": "Python Trader"})
    assert tip(state, None).startswith("torus drive is mass locked: Python Trader is on your")
    state.apply({"type": "mass_lock", "by": "planet"})
    assert "close to the planet" in tip(state, None)
    state.apply({"type": "mass_lock", "by": None})
    assert tip(state, None) == ""
    state.apply({"type": "mass_lock", "by": "planet"})
    state.apply({"type": "docked"})
    assert state.mass_lock is None


def test_drive_indicators_follow_mass_lock_and_jump_blocker_in_flight():
    from helper.contexts import indicators
    from helper.state import GameState

    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 1})
    assert indicators(state) == [("TORUS", True, ""), ("JUMP", True, "")]
    state.apply({"type": "mass_lock", "by": "planet"})
    state.apply({"type": "jump_blocker", "by": "Coriolis Station", "clearAt": 6747})
    assert indicators(state) == [("TORUS", False, "planet"), ("JUMP", False, "Coriolis Station")]
    state.apply({"type": "docked"})
    assert indicators(state) == []


def test_clearance_badge_by_status_with_the_players_key():
    from helper.contexts import clearance_badge
    from helper.state import GameState

    class Keys:
        def keys(self, action):
            return "Shift+L" if action == "key_docking_clearance_request" else ""

    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 1})
    assert clearance_badge(state, Keys()) is None  # not near a station
    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "station": "Lave Station",
            "requiresClearance": True,
            "clearance": "DOCKING_CLEARANCE_STATUS_NONE",
        }
    )
    assert clearance_badge(state, Keys()) == ("No clearance", "red", False)
    state.apply({"type": "clearance", "status": "DOCKING_CLEARANCE_STATUS_TIMING_OUT"})
    assert clearance_badge(state, Keys()) == (
        "Clearance expiring: press Shift+L to extend",
        "amber",
        True,
    )
    state.apply(
        {"type": "clearance", "status": "DOCKING_CLEARANCE_STATUS_NONE", "event": "refused"}
    )
    assert clearance_badge(state, Keys())[:2] == ("Clearance refused", "red")
    state.requires_clearance = False
    assert clearance_badge(state, Keys()) == ("No clearance needed", "green", False)
