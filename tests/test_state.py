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


def test_clearance_details_and_station_without_clearance():
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
    assert state.details == ["Clearance: granted", "Docking computer on"]

    state.apply(
        {
            "type": "aegis",
            "inside": True,
            "station": "Outpost",
            "requiresClearance": False,
            "clearance": "DOCKING_CLEARANCE_STATUS_NONE",
        }
    )
    assert state.details == ["Outpost: clearance not required", "Docking computer on"]


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
        "combat": ["flying", "red alert", "flying"],
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
