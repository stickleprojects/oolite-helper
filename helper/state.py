"""Game state built up from the add-on's messages, and the context it implies."""


class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.docked = None
        self.gui = None

    def apply(self, msg):
        kind = msg.get("type")
        if kind == "hello":  # a new game session started
            self.reset()
        elif kind == "ready":
            self.docked = msg.get("docked")
        elif kind == "docked":
            self.docked = True
        elif kind == "launching":
            self.docked = False
        elif kind == "gui":
            self.gui = msg.get("to")

    @property
    def context(self):
        if self.docked is None:
            return "unknown"
        if self.docked:
            return "docked"
        if self.gui and self.gui != "GUI_SCREEN_MAIN":
            return "menu"
        return "flying"
