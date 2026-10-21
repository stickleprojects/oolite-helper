"""Which key actions to show for the current game state.

Only action names live here. The keys themselves and their descriptions always
come from the player's keymap (see keys.py).
"""

STATION_SCREENS = ("Station", [
    "key_launch_ship", "key_gui_screen_status", "key_gui_chart_screens",
    "key_gui_system_data", "key_gui_market", "key_gui_screen_equipship",
    "key_gui_screen_interfaces", "key_gui_screen_options",
])
FLIGHT_SCREENS = ("Screens", [
    "key_gui_screen_status", "key_gui_chart_screens", "key_gui_system_data",
    "key_gui_market", "key_view_forward",
])
MENU_NAV = ("Menu", [
    "key_gui_arrow_up", "key_gui_arrow_down", "key_gui_arrow_left",
    "key_gui_arrow_right", "key_gui_select", "key_gui_page_up", "key_gui_page_down",
])
FLIGHT = ("Flight", [
    "key_roll_left", "key_roll_right", "key_pitch_forward", "key_pitch_back",
    "key_yaw_left", "key_yaw_right", "key_increase_speed", "key_decrease_speed",
    "key_inject_fuel",
])
VIEWS = ("Views", [
    "key_view_forward", "key_view_aft", "key_view_port", "key_view_starboard",
    "key_custom_view",
])
TARGETING = ("Targeting", [
    "key_next_target", "key_previous_target", "key_ident_system",
    "key_next_compass_mode", "key_scanner_zoom",
])
TRAVEL = ("Travel", [
    "key_jumpdrive", "key_hyperspace", "key_galactic_hyperspace",
    "key_autopilot", "key_docking_clearance_request",
])
MISC = ("Other", [
    "key_pausebutton", "key_comms_log", "key_hud_toggle", "key_snapshot",
])
DOCKING = ("Docking", [
    "key_docking_clearance_request", "key_autopilot", "key_autodock",
    "key_decrease_speed", "key_docking_music",
])
COMBAT = ("Combat", [
    "key_weapons_online_toggle", "key_fire_lasers", "key_target_missile",
    "key_launch_missile", "key_next_missile", "key_untarget_missile",
    "key_target_incoming_missile", "key_ecm", "key_next_target",
])
ESCAPE = ("Escape", [
    "key_inject_fuel", "key_jumpdrive", "key_dump_cargo", "key_launch_escapepod",
])
JUMP = ("Jump", [
    "key_hyperspace", "key_galactic_hyperspace", "key_gui_chart_screens",
])
CHART = ("Chart", [
    "key_gui_chart_screens", "key_map_zoom_in", "key_map_zoom_out",
    "key_map_home", "key_map_end", "key_map_next_system",
    "key_map_previous_system", "key_map_info", "key_chart_highlight",
    "key_advanced_nav_array_next", "key_advanced_nav_array_previous",
])
PLANET_INFO = ("Planet info", [
    "key_system_home", "key_system_end", "key_system_next_system",
    "key_system_previous_system",
])
MARKET = ("Market", [
    "key_gui_arrow_up", "key_gui_arrow_down", "key_market_buy_one",
    "key_market_sell_one", "key_market_buy_max", "key_market_sell_max",
    "key_market_filter_cycle", "key_market_sorter_cycle",
])

SCREEN_SECTIONS = {
    "GUI_SCREEN_SHORT_RANGE_CHART": [CHART],
    "GUI_SCREEN_LONG_RANGE_CHART": [CHART],
    "GUI_SCREEN_SYSTEM_DATA": [PLANET_INFO],
    "GUI_SCREEN_MARKET": [MARKET],
}


# Tips per context. {key_x} is replaced with that action's real keys. Each one
# is backed by the game source (PlayerEntityControls.m, 1.92.1).
TIPS = {
    # performDockingRequest: is called with the primary target only.
    "near station": "{key_docking_clearance_request} asks your current target, so target "
                    "the station first ({key_ident_system} with it ahead, or {key_next_target}).",
    # The hyperspace key during a countdown calls cancelWitchspaceCountdown.
    "jump countdown": "Press {key_hyperspace} again to cancel the countdown.",
}


# Short qualifiers shown after an action's description, for keys that share a
# binding with another action and only apply in one mode.
ACTION_NOTES = {
    # Only read in pollAutopilotControls; otherwise the same key is thrust.
    "key_docking_music": "while docking computer is on",
}


def tip(state, keymap):
    text = TIPS.get(state.context)
    if not text:
        return ""
    return text.format_map(_KeysLookup(keymap))


class _KeysLookup(dict):
    def __init__(self, keymap):
        super().__init__()
        self.keymap = keymap

    def __missing__(self, action):
        return self.keymap.keys(action) or "(unbound)"


def sections(state):
    """List of (title, [action, ...]) for the current state."""
    context = state.context
    screen_sections = SCREEN_SECTIONS.get(state.gui, [MENU_NAV])
    if context == "docked":
        if state.gui in SCREEN_SECTIONS:
            return screen_sections + [STATION_SCREENS]
        return [STATION_SCREENS, MENU_NAV]
    if context == "menu":
        return screen_sections + [FLIGHT_SCREENS]
    if context == "jump countdown":
        return [JUMP, FLIGHT, VIEWS]
    if context == "red alert":
        return [COMBAT, ESCAPE, FLIGHT, VIEWS]
    if context == "near station":
        return [DOCKING, FLIGHT, TARGETING, VIEWS, FLIGHT_SCREENS]
    if context == "flying":
        return [FLIGHT, VIEWS, TARGETING, TRAVEL, FLIGHT_SCREENS, MISC]
    return []
