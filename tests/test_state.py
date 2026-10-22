from pathlib import Path

from helper.state import GameState
from tests.fakegame import load_scenario

ROOT = Path(__file__).resolve().parents[1]


class FakeClock:
    def __init__(self, now=0):
        self.now = now

    def __call__(self):
        return self.now


def test_context_precedence_from_docked_to_flying():
    state = GameState()
    state.apply({"type": "ready", "docked": False, "alert": 3})
    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "station": "Lave Station",
            "requiresClearance": True,
        }
    )
    assert state.context == "red alert"

    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    assert state.context == "jump countdown"
    state.apply({"type": "gui", "to": "GUI_SCREEN_STATUS"})
    assert state.context == "menu"
    state.apply({"type": "docked"})
    assert state.context == "docked"
    state.apply({"type": "launching"})
    assert state.context == "menu"
    state.apply({"type": "gui", "to": "GUI_SCREEN_MAIN"})
    assert state.context == "red alert"
    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "station": "Lave Station",
            "requiresClearance": True,
        }
    )
    state.apply({"type": "alert", "level": 1})
    assert state.context == "near station"
    state.apply({"type": "aegis", "inside": False})
    assert state.context == "flying"


def test_session_hello_and_closed_reset_state():
    for message in ({"type": "session"}, {"type": "hello"}):
        state = GameState()
        state.apply({"type": "ready", "docked": True, "view": "VIEW_AFT", "alert": 3})
        state.apply({"type": "autopilot", "on": True})
        state.apply(message)
        assert state.context == "waiting for game"
        assert state.view is None
        assert state.autopilot is False
        assert state.details == []

    state = GameState()
    state.apply({"type": "ready", "docked": True, "alert": 3})
    state.apply({"type": "closed"})
    assert state.context == "game not running"
    assert state.docked is None
    assert state.alert is None
    state.apply({"type": "session"})
    assert state.context == "waiting for game"


def test_clearance_is_left_to_the_badge_and_refusal_is_remembered():
    state = GameState()
    state.apply({"type": "ready", "docked": False})
    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "station": "Lave Station",
            "requiresClearance": True,
            "clearance": "DOCKING_CLEARANCE_STATUS_GRANTED",
        }
    )
    state.apply({"type": "autopilot", "on": True})
    assert state.details == ["Docking computer on"]
    state.apply(
        {"type": "clearance", "status": "DOCKING_CLEARANCE_STATUS_NONE", "event": "refused"}
    )
    assert state.clearance_refused
    state.apply({"type": "clearance", "status": "DOCKING_CLEARANCE_STATUS_REQUESTED"})
    assert not state.clearance_refused

    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "station": "Outpost",
            "requiresClearance": False,
            "clearance": "DOCKING_CLEARANCE_STATUS_NONE",
        }
    )
    assert state.requires_clearance is False


def test_countdown_uses_injected_clock_and_stops_at_zero():
    clock = FakeClock(10)
    state = GameState(clock=clock)
    state.apply({"type": "countdown", "kind": "galactic", "seconds": 20})
    assert state.countdown_left == 20
    clock.now = 14.25
    assert state.countdown_left == 15.75
    assert state.details == ["Galactic jump in 16s"]
    clock.now = 40
    assert state.countdown_left == 0
    state.apply({"type": "countdown_end"})
    assert state.countdown_left is None
    assert state.details == []


def test_fake_game_scenarios_drive_expected_contexts():
    expected = {
        "combat": ["flying", "flying", "red alert", "flying"],
        "docking": [
            "docked",
            "flying",
            "near station",
            "near station",
            "near station",
            "near station",
            "near station",
            "docked",
        ],
        "jump": [
            "flying",
            "menu",
            "flying",
            "jump countdown",
            "flying",
            "jump countdown",
            "flying",
            "flying",
        ],
        "menus": ["flying", "menu", "menu", "flying", "flying"],
        "restart": ["flying", "red alert", "docked", "docked"],
        "death": ["flying", "red alert", "ship destroyed", "waiting for game", "docked"],
    }
    for name, contexts in expected.items():
        state = GameState()
        messages = [
            step["msg"]
            for step in load_scenario(ROOT / "scenarios" / f"{name}.yaml")
            if "msg" in step
        ]
        assert len(messages) == len(contexts)
        for message, context in zip(messages, contexts, strict=True):
            state.apply(message)
            assert state.context == context, (name, message)


def test_death_clears_flight_state_until_a_game_loads():
    state = GameState(clock=FakeClock())
    state.apply({"type": "ready", "docked": False, "alert": 3})
    state.apply({"type": "aegis", "inside": True, "station": "Lave Station"})
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    state.apply({"type": "died", "cause": "energy damage", "by": "Krait"})
    assert state.context == "ship destroyed"
    assert state.details == ["Destroyed by Krait (energy damage)"]
    assert not state.in_aegis and state.countdown_left is None

    state.apply({"type": "died", "cause": None, "by": None})
    assert state.details == ["Destroyed"]

    state.apply({"type": "ready", "docked": True, "alert": 0})
    assert state.context == "docked"
    assert state.details == []


def test_galaxy_comes_from_systems_and_market_messages():
    state = GameState()
    state.apply({"type": "systems", "galaxy": 2, "fuel": 7, "systems": []})
    assert state.galaxy == 2
    state.apply({"type": "systems", "fuel": 7, "systems": []})  # older add-on: keep it
    assert state.galaxy == 2
    state.apply({"type": "market", "galaxy": 3, "market": {}})
    assert state.galaxy == 3


def test_a_blocked_jump_says_why_until_the_next_try():
    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 1})
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    state.apply({"type": "countdown_end", "reason": "blocked"})
    assert any(note.startswith("Jump blocked") for note in state.details)
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    assert not any("blocked" in note for note in state.details)
    state.apply({"type": "countdown_end", "reason": "cancelled"})
    assert state.jump_failed is None


def test_heading_says_where_you_are_and_whether_it_was_the_jump_target():
    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 1})
    state.apply(
        {"type": "systems", "galaxy": 0, "fuel": 7, "systems": [{"id": 8, "name": "Qutiri"}]}
    )
    state.apply({"type": "chart_target", "targetSystem": 8, "currentSystem": 154})
    state.system_name = "Isinor"
    assert state.where == ("Isinor", False, None)
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    state.apply({"type": "countdown_end", "reason": "jumped"})
    state.apply({"type": "arrived", "system": "Qutiri", "alert": 1})
    state.apply({"type": "chart_target", "targetSystem": 8, "currentSystem": 8})
    assert state.where == ("Qutiri", True, None)
    state.apply({"type": "launching"})
    assert state.where == ("Qutiri", False, None)


def test_a_jump_that_lands_elsewhere_says_where_it_was_aimed():
    state = GameState(clock=lambda: 0)
    state.apply({"type": "ready", "docked": False, "alert": 1})
    state.apply({"type": "systems", "systems": [{"id": 8, "name": "Qutiri"}]})
    state.apply({"type": "chart_target", "targetSystem": 8, "currentSystem": 154})
    state.apply({"type": "countdown", "kind": "standard", "seconds": 15})
    state.apply({"type": "arrived", "system": "Interstellar space", "alert": 3})
    state.apply({"type": "chart_target", "targetSystem": 8, "currentSystem": 200})
    assert state.where == ("Interstellar space", False, "Qutiri")


def test_equipment_is_replaced_by_each_message_and_cleared_by_a_new_game():
    state = GameState()
    ecm = {"key": "EQ_ECM", "name": "E.C.M. System", "count": 1, "status": "EQUIPMENT_OK"}
    missiles = {"capacity": 4, "loaded": [{"key": "EQ_MISSILE", "name": "Missile", "count": 1}]}
    state.apply({"type": "equipment", "items": [ecm], "missiles": missiles})
    assert state.equipment == [ecm]
    assert state.missiles == missiles
    state.apply({"type": "equipment", "items": []})
    assert state.equipment == []
    state.apply({"type": "equipment", "items": [ecm]})
    state.apply({"type": "hello"})
    assert state.equipment == []
    assert state.missiles is None
