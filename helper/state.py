"""Game state built up from the add-on's messages, and the context it implies."""

import time

ALERT_RED = 3


class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.docked = None
        self.gui = None
        self.view = None
        self.game_closed = False
        self.alert = None
        self.in_aegis = False
        self.station = None
        self.requires_clearance = None
        self.clearance = None
        self.autopilot = False
        self.countdown_kind = None
        self.countdown_ends = None  # time.monotonic() when the jump happens
        self.market_station = None
        self.market = None
        self.credits = None
        self.cargo_space = None
        self.fuel = None
        self.manifest = None
        self.last_trade = None
        self.systems = []
        self.info_system = None
        self.target_system = None

    def apply(self, msg):
        kind = msg.get("type")
        if kind in ("session", "hello"):  # new log file / game loaded
            self.reset()
        elif kind == "ready":
            self.docked = msg.get("docked")
            self.view = msg.get("view")
            self.alert = msg.get("alert")
        elif kind == "docked":
            self.docked = True
            self.in_aegis = False
            self.autopilot = False
            self.clearance = None
            self.end_countdown()
        elif kind == "launching":
            self.docked = False
        elif kind == "gui":
            self.gui = msg.get("to")
        elif kind == "view":
            self.view = msg.get("to")
        elif kind == "aegis":
            self.in_aegis = bool(msg.get("inside"))
            self.station = msg.get("station")
            self.requires_clearance = msg.get("requiresClearance")
            self.clearance = msg.get("clearance")
        elif kind == "clearance":
            self.clearance = msg.get("status")
        elif kind == "autopilot":
            self.autopilot = bool(msg.get("on"))
        elif kind == "alert":
            self.alert = msg.get("level")
        elif kind == "countdown":
            self.countdown_kind = msg.get("kind")
            self.countdown_ends = time.monotonic() + float(msg.get("seconds") or 0)
        elif kind == "countdown_end":
            self.end_countdown()
        elif kind == "arrived":
            self.end_countdown()
            self.alert = msg.get("alert")
        elif kind == "market":
            self.market_station = msg.get("station")
            self.market = msg.get("market")
            self.credits = msg.get("credits")
            self.cargo_space = msg.get("cargoSpace")
            self.fuel = msg.get("fuel")
            self.manifest = msg.get("manifest")
        elif kind in ("bought", "sold"):
            self.last_trade = msg
        elif kind == "systems":
            self.fuel = msg.get("fuel")
            self.systems = msg.get("systems", [])
        elif kind == "chart_target":
            self.info_system = msg.get("infoSystem")
            self.target_system = msg.get("targetSystem")
        elif kind == "closed":
            self.reset()
            self.game_closed = True

    def end_countdown(self):
        self.countdown_kind = None
        self.countdown_ends = None

    @property
    def countdown_left(self):
        if self.countdown_ends is None:
            return None
        return max(0, self.countdown_ends - time.monotonic())

    @property
    def context(self):
        if self.game_closed:
            return "game not running"
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
        """Short status notes for the header, e.g. clearance and autopilot."""
        notes = []
        if self.countdown_left is not None:
            jump = "Galactic jump" if self.countdown_kind == "galactic" else "Jump"
            notes.append(f"{jump} in {self.countdown_left:.0f}s")
        if self.in_aegis and not self.docked:
            if self.requires_clearance is False:
                notes.append(f"{self.station or 'Station'}: clearance not required")
            elif self.clearance:
                status = self.clearance.replace("DOCKING_CLEARANCE_STATUS_", "").replace("_", " ")
                notes.append(f"Clearance: {status.lower()}")
        if self.autopilot:
            notes.append("Docking computer on")
        return notes
