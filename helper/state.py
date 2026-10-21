"""Game state built up from the add-on's messages, and the context it implies."""


class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.docked = None
        self.gui = None
        self.view = None

    def apply(self, msg):
        kind = msg.get("type")
        if kind in ("session", "hello"):  # new log file / game loaded
            self.reset()
        elif kind == "ready":
            self.docked = msg.get("docked")
            self.view = msg.get("view")
        elif kind == "docked":
            self.docked = True
        elif kind == "launching":
            self.docked = False
        elif kind == "gui":
            self.gui = msg.get("to")
        elif kind == "view":
            self.view = msg.get("to")

    @property
    def context(self):
        if self.docked is None:
            return "waiting for game"
        if self.docked:
            return "docked"
        if self.gui and self.gui != "GUI_SCREEN_MAIN":
            return "menu"
        return "flying"
