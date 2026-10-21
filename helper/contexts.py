"""Which key actions to show for the current game state.

Only action names live here. The keys themselves and their descriptions always
come from the player's keymap (see keys.py).
"""

from .trade import chart_advice

STATION_SCREENS = (
    "Station",
    [
        "key_launch_ship",
        "key_gui_screen_status",
        "key_gui_chart_screens",
        "key_gui_system_data",
        "key_gui_market",
        "key_gui_screen_equipship",
        "key_gui_screen_interfaces",
        "key_gui_screen_options",
    ],
)
FLIGHT_SCREENS = (
    "Screens",
    [
        "key_gui_screen_status",
        "key_gui_chart_screens",
        "key_gui_system_data",
        "key_gui_market",
        "key_view_forward",
    ],
)
MENU_NAV = (
    "Menu",
    [
        "key_gui_arrow_up",
        "key_gui_arrow_down",
        "key_gui_arrow_left",
        "key_gui_arrow_right",
        "key_gui_select",
        "key_gui_page_up",
        "key_gui_page_down",
    ],
)
FLIGHT = (
    "Flight",
    [
        "key_roll_left",
        "key_roll_right",
        "key_pitch_forward",
        "key_pitch_back",
        "key_yaw_left",
        "key_yaw_right",
        "key_increase_speed",
        "key_decrease_speed",
        "key_inject_fuel",
    ],
)
VIEWS = (
    "Views",
    [
        "key_view_forward",
        "key_view_aft",
        "key_view_port",
        "key_view_starboard",
        "key_custom_view",
    ],
)
TARGETING = (
    "Targeting",
    [
        "key_next_target",
        "key_previous_target",
        "key_ident_system",
        "key_next_compass_mode",
        "key_scanner_zoom",
    ],
)
TRAVEL = (
    "Travel",
    [
        "key_jumpdrive",
        "key_hyperspace",
        "key_galactic_hyperspace",
        "key_autopilot",
        "key_docking_clearance_request",
    ],
)
DOCKING = (
    "Docking",
    [
        "key_docking_clearance_request",
        "key_autopilot",
        "key_autodock",
        "key_decrease_speed",
        "key_docking_music",
    ],
)
# For flying and near a station: you may start a fight before any red alert.
WEAPONS = (
    "Weapons",
    [
        "key_weapons_online_toggle",
        "key_fire_lasers",
        "key_target_missile",
        "key_launch_missile",
        "key_untarget_missile",
        "key_ecm",
    ],
)
COMBAT = (
    "Combat",
    [
        "key_weapons_online_toggle",
        "key_fire_lasers",
        "key_target_missile",
        "key_launch_missile",
        "key_next_missile",
        "key_untarget_missile",
        "key_target_incoming_missile",
        "key_ecm",
        "key_next_target",
    ],
)
ESCAPE = (
    "Escape",
    [
        "key_inject_fuel",
        "key_jumpdrive",
        "key_dump_cargo",
        "key_launch_escapepod",
    ],
)
JUMP = (
    "Jump",
    [
        "key_hyperspace",
        "key_galactic_hyperspace",
        "key_gui_chart_screens",
    ],
)
CHART = (
    "Chart",
    [
        "key_gui_chart_screens",
        "key_map_zoom_in",
        "key_map_zoom_out",
        "key_map_home",
        "key_map_end",
        "key_map_next_system",
        "key_map_previous_system",
        "key_map_info",
        "key_chart_highlight",
        "key_advanced_nav_array_next",
        "key_advanced_nav_array_previous",
    ],
)
PLANET_INFO = (
    "Planet info",
    [
        "key_system_home",
        "key_system_end",
        "key_system_next_system",
        "key_system_previous_system",
    ],
)
MARKET = (
    "Market",
    [
        "key_gui_arrow_up",
        "key_gui_arrow_down",
        "key_market_buy_one",
        "key_market_sell_one",
        "key_market_buy_max",
        "key_market_sell_max",
        "key_market_filter_cycle",
        "key_market_sorter_cycle",
    ],
)

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
    # pollGameOverControls checks Space directly (not a key binding); after
    # kDeadResetTime (30 s) handleGameOver reloads the last save anyway.
    "ship destroyed": "Press Space, or wait 30 seconds, and the game reloads your last save.",
}


# Short qualifiers shown after an action's description, for keys that share a
# binding with another action and only apply in one mode.
ACTION_NOTES = {
    # Only read in pollAutopilotControls; otherwise the same key is thrust.
    "key_docking_music": "while docking computer is on",
}


# Near-station tips by clearance status, from StationEntity
# acceptDockingClearanceRequestFrom: — the request key extends clearance while
# it's timing out, but cancels it while it's granted or requested.
CLEARANCE_TIPS = {
    "DOCKING_CLEARANCE_STATUS_TIMING_OUT": (
        "Clearance is about to expire: press {key_docking_clearance_request} now to extend it."
    ),
    "DOCKING_CLEARANCE_STATUS_GRANTED": (
        "Cleared to dock. Pressing {key_docking_clearance_request} again cancels clearance."
    ),
    "DOCKING_CLEARANCE_STATUS_REQUESTED": (
        "Waiting for clearance. Pressing {key_docking_clearance_request} again cancels the request."
    ),
    "DOCKING_CLEARANCE_STATUS_NOT_REQUIRED": "No clearance needed here.",
}


def tip(state, keymap):
    if state.gui in ("GUI_SCREEN_SHORT_RANGE_CHART", "GUI_SCREEN_LONG_RANGE_CHART"):
        return chart_advice(state)
    text = TIPS.get(state.context)
    if state.context == "near station":
        text = CLEARANCE_TIPS.get(state.clearance, text)
    if not text or not keymap:
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
        return [DOCKING, FLIGHT, TARGETING, WEAPONS, VIEWS, FLIGHT_SCREENS]
    if context == "flying":
        return [FLIGHT, VIEWS, TARGETING, WEAPONS, TRAVEL, FLIGHT_SCREENS]
    return []


# Every action, grouped as on the game's keyboard configuration screen
# (PlayerEntityKeyMapper.m keyFunctionList, 1.92.1). Group titles come from
# descriptions.plist "oolite-keydesc-header-*" via the keymap.
ALL_KEY_GROUPS = [
    (
        "header-screen-access",
        [
            "key_launch_ship",
            "key_gui_screen_options",
            "key_gui_screen_equipship",
            "key_gui_screen_interfaces",
            "key_gui_screen_status",
            "key_gui_chart_screens",
            "key_gui_system_data",
            "key_gui_market",
        ],
    ),
    (
        "header-propulsion",
        [
            "key_roll_left",
            "key_roll_right",
            "key_pitch_forward",
            "key_pitch_back",
            "key_yaw_left",
            "key_yaw_right",
            "key_increase_speed",
            "key_decrease_speed",
            "key_inject_fuel",
            "key_jumpdrive",
            "key_hyperspace",
            "key_galactic_hyperspace",
        ],
    ),
    (
        "header-navigation",
        [
            "key_next_compass_mode",
            "key_prev_compass_mode",
            "key_scanner_zoom",
            "key_scanner_unzoom",
            "key_view_forward",
            "key_view_aft",
            "key_view_port",
            "key_view_starboard",
            "key_ident_system",
            "key_docking_clearance_request",
            "key_autopilot",
            "key_autodock",
            "key_docking_music",
        ],
    ),
    (
        "header-offensive",
        [
            "key_weapons_online_toggle",
            "key_fire_lasers",
            "key_launch_missile",
            "key_target_missile",
            "key_untarget_missile",
            "key_target_incoming_missile",
            "key_next_missile",
            "key_next_target",
            "key_previous_target",
        ],
    ),
    (
        "header-defensive",
        [
            "key_ecm",
            "key_dump_cargo",
            "key_rotate_cargo",
            "key_launch_escapepod",
        ],
    ),
    (
        "header-special-equip",
        [
            "key_cycle_next_mfd",
            "key_cycle_previous_mfd",
            "key_switch_next_mfd",
            "key_switch_previous_mfd",
            "key_prime_next_equipment",
            "key_prime_previous_equipment",
            "key_activate_equipment",
            "key_mode_equipment",
            "key_fastactivate_equipment_a",
            "key_fastactivate_equipment_b",
        ],
    ),
    (
        "header-chart-screen",
        [
            "key_advanced_nav_array_next",
            "key_advanced_nav_array_previous",
            "key_map_home",
            "key_map_end",
            "key_map_info",
            "key_map_zoom_in",
            "key_map_zoom_out",
            "key_map_next_system",
            "key_map_previous_system",
            "key_chart_highlight",
        ],
    ),
    (
        "header-planet-info-screen",
        [
            "key_system_home",
            "key_system_end",
            "key_system_next_system",
            "key_system_previous_system",
        ],
    ),
    (
        "header-market-screen",
        [
            "key_market_filter_cycle",
            "key_market_sorter_cycle",
            "key_market_buy_one",
            "key_market_sell_one",
            "key_market_buy_max",
            "key_market_sell_max",
        ],
    ),
    (
        "header-misc",
        [
            "key_snapshot",
            "key_pausebutton",
            "key_show_fps",
            "key_bloom_toggle",
            "key_mouse_control_roll",
            "key_mouse_control_yaw",
            "key_hud_toggle",
            "key_inc_field_of_view",
            "key_dec_field_of_view",
            "key_comms_log",
        ],
    ),
    (
        "header-custom-view",
        [
            "key_custom_view",
            "key_custom_view_zoom_in",
            "key_custom_view_zoom_out",
            "key_custom_view_roll_left",
            "key_custom_view_roll_right",
            "key_custom_view_pan_left",
            "key_custom_view_pan_right",
            "key_custom_view_pan_up",
            "key_custom_view_pan_down",
            "key_custom_view_rotate_left",
            "key_custom_view_rotate_right",
            "key_custom_view_rotate_up",
            "key_custom_view_rotate_down",
        ],
    ),
    (
        "header-oxz-manager",
        [
            "key_oxzmanager_setfilter",
            "key_oxzmanager_showinfo",
            "key_oxzmanager_extract",
        ],
    ),
    (
        "header-gui",
        [
            "key_gui_arrow_left",
            "key_gui_arrow_right",
            "key_gui_arrow_up",
            "key_gui_arrow_down",
            "key_gui_page_down",
            "key_gui_page_up",
            "key_gui_select",
        ],
    ),
    (
        "header-debug",
        [
            "key_dump_target_state",
            "key_dump_entity_list",
            "key_debug_full",
            "key_debug_collision",
            "key_debug_console_connect",
            "key_debug_bounding_boxes",
            "key_debug_shaders",
            "key_debug_off",
        ],
    ),
]
