"""Game state built up from the add-on's messages, and the context it implies."""

import time

ALERT_RED = 3
# playerJumpFailed reasons (PlayerEntity.m witchJumpChecklist:, 1.92.1) and what to do.
JUMP_FAILED = {
    # checkShipsInVicinityForWitchJumpExit: blocked while 0.1 x mass > distance squared
    # (about 7 km from a Coriolis station); nothing off the scanner blocks.
    "blocked": "Jump blocked: a station or big ship is too close. Fly until it's off "
    "the scanner, then try again",
    "too far": "Jump failed: the target is out of range",
    "insufficient fuel": "Jump failed: not enough fuel",
    "malfunction": "Jump failed: the hyperdrive is damaged",
    "no target": "Jump failed: no target system",
}


class GameState:
    def __init__(self, clock=None):
        self._clock = clock if clock is not None else time.monotonic
        self.reset()

    def reset(self):
        self.docked = None
        self.gui = None
        self.view = None
        self.game_closed = False
        self.died = None  # the "died" message until a game is loaded
        self.alert = None
        self.in_aegis = False
        self.station = None
        self.requires_clearance = None
        self.clearance = None
        self.clearance_refused = False  # the station refused the last request
        self.autopilot = False
        self.countdown_kind = None
        self.countdown_ends = None  # time.monotonic() when the jump happens
        self.jump_failed = None  # reason the last jump failed, until the next try
        self.jump_blocker = None  # {"by", "clearAt"} while a nearby mass would block a jump
        self.mass_lock = None  # what locks the torus drive: a ship's name, "planet" or "sun"
        self.market_station = None
        self.market = None
        self.credits = None
        self.cargo_space = None
        self.fuel = None
        self.manifest = None
        self.last_trade = None
        self.systems = []
        self.galaxy = None
        self.info_system = None
        self.target_system = None
        self.chart_system = None
        self.current_system = None
        self.system_name = None  # the system the player is in
        self.jump_destination = None  # (id, name) the last jump was aimed at, until launch
        self.origin_market = {}
        # fitted: [{"key", "name", "description", "count", "status", "provides"}],
        # or None before the add-on says (older add-ons never do)
        self.equipment = None
        self.missiles = None  # {"capacity": pylons, "loaded": [{"key", "name", "count"}]}

    def apply(self, msg):
        kind = msg.get("type")
        if kind in ("session", "hello"):  # new log file / game loaded
            self.reset()
        elif kind == "died":
            self.reset()
            self.died = msg
        elif kind == "ready":
            self.died = None
            self.docked = msg.get("docked")
            self.view = msg.get("view")
            self.alert = msg.get("alert")
        elif kind == "docked":
            self.docked = True
            self.jump_blocker = self.mass_lock = None
            self.in_aegis = False
            self.autopilot = False
            self.clearance = None
            self.end_countdown()
        elif kind == "launching":
            self.docked = False
            self.jump_destination = None
        elif kind == "jump_blocker":
            self.jump_blocker = msg if msg.get("by") else None
        elif kind == "mass_lock":
            self.mass_lock = msg.get("by")
        elif kind == "gui":
            self.gui = msg.get("to")
        elif kind == "view":
            self.view = msg.get("to")
        elif kind == "aegis":
            self.in_aegis = bool(msg.get("inside"))
            self.station = msg.get("station")
            self.requires_clearance = msg.get("requiresClearance")
            self.clearance = msg.get("clearance")
            self.clearance_refused = False
        elif kind == "clearance":
            self.clearance = msg.get("status")
            self.clearance_refused = msg.get("event") == "refused"
        elif kind == "autopilot":
            self.autopilot = bool(msg.get("on"))
        elif kind == "alert":
            self.alert = msg.get("level")
        elif kind == "countdown":
            self.jump_destination = self._target()
            self.countdown_kind = msg.get("kind")
            self.countdown_ends = self._clock() + float(msg.get("seconds") or 0)
            self.jump_failed = None
        elif kind == "countdown_end":
            self.end_countdown()
            self.jump_failed = msg.get("reason") if msg.get("reason") in JUMP_FAILED else None
        elif kind == "arrived":
            self.system_name = msg.get("system", self.system_name)
            self.end_countdown()
            self.jump_failed = None
            self.alert = msg.get("alert")
        elif kind == "market":
            self.galaxy = msg.get("galaxy", self.galaxy)
            self.current_system = msg.get("systemID", self.current_system)
            self.system_name = msg.get("systemName", self.system_name)
            self.market_station = msg.get("station")
            self.market = msg.get("market")
            self.credits = msg.get("credits")
            self.cargo_space = msg.get("cargoSpace")
            self.fuel = msg.get("fuel")
            self.manifest = msg.get("manifest")
        elif kind in ("bought", "sold"):
            self.last_trade = msg
        elif kind == "systems":
            self.galaxy = msg.get("galaxy", self.galaxy)
            self.fuel = msg.get("fuel")
            self.systems = msg.get("systems", [])
        elif kind == "chart_target":
            self.info_system = msg.get("infoSystem")
            self.target_system = msg.get("targetSystem")
            self.chart_system = msg.get("system")
            self.current_system = msg.get("currentSystem")
            self.origin_market = msg.get("originMarket") or {}
            self.manifest = msg.get("manifest", self.manifest)
        elif kind == "equipment":
            self.equipment = msg.get("items") or []
            self.missiles = msg.get("missiles")
        elif kind == "closed":
            self.reset()
            self.game_closed = True

    @property
    def fitted(self):
        """Equipment keys the game's checks accept, or None before the add-on says.

        The game asks hasEquipmentItemProviding: (ShipEntity, 1.92.1), which
        counts what working items provide too; a damaged item is stored as
        EQ_..._DAMAGED, so it doesn't count.
        """
        if self.equipment is None:
            return None
        keys = set()
        for item in self.equipment:
            if item.get("status") != "EQUIPMENT_DAMAGED":
                keys.add(item.get("key"))
                keys.update(item.get("provides") or ())
        return keys

    def _target(self):
        """(id, name) of the jump target, with its name from the systems in range."""
        target = self.target_system
        if target is None:
            return None
        name = next((s.get("name") for s in self.systems if s.get("id") == target), None)
        return target, name

    @property
    def where(self):
        """(system name, reached_target, aimed_at) for the heading; name may be None.

        reached_target is True when this is where the last jump was aimed, and
        aimed_at names the intended system when a jump landed elsewhere.
        """
        destination = self.jump_destination
        if destination is None or self.current_system is None:
            return self.system_name, False, None
        if destination[0] == self.current_system:
            return self.system_name, True, None
        return self.system_name, False, destination[1]

    def end_countdown(self):
        self.countdown_kind = None
        self.countdown_ends = None

    @property
    def countdown_left(self):
        if self.countdown_ends is None:
            return None
        return max(0, self.countdown_ends - self._clock())

    @property
    def context(self):
        if self.game_closed:
            return "game not running"
        if self.died is not None:
            return "ship destroyed"
        if self.docked is None:
            return "waiting for game"
        if self.docked:
            return "docked"
        if self.gui and self.gui != "GUI_SCREEN_MAIN":
            return "menu"
        if self.countdown_kind:
            return "jump countdown"
        if self.alert == ALERT_RED:
            return "red alert"
        if self.in_aegis:
            return "near station"
        return "flying"

    @property
    def details(self):
        """Short status notes for the header, e.g. a countdown or the autopilot.

        Docking clearance has its own badge (contexts.clearance_badge).
        """
        return [text for _, _, text in self.detail_items]

    @property
    def detail_items(self):
        """(kind, fields, text) for each note: plugins get the kind and fields
        as constants beside the English text (#59)."""
        items = []
        if self.died is not None:
            by, cause = self.died.get("by"), self.died.get("cause")
            text = f"Destroyed by {by}" if by else "Destroyed"
            items.append(
                ("destroyed", {"by": by, "cause": cause}, f"{text} ({cause})" if cause else text)
            )
        if self.countdown_left is not None:
            galactic = self.countdown_kind == "galactic"
            jump = "Galactic jump" if galactic else "Jump"
            text = f"{jump} in {self.countdown_left:.0f}s"
            seconds = int(f"{self.countdown_left:.0f}")
            items.append(("countdown", {"galactic": galactic, "seconds": seconds}, text))
        if self.jump_failed and not self.docked:
            items.append(
                ("jump_failed", {"reason": self.jump_failed}, JUMP_FAILED[self.jump_failed])
            )
        if self.autopilot:
            items.append(("docking_computer", {}, "Docking computer on"))
        return items
