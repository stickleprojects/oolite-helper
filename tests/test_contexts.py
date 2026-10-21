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
