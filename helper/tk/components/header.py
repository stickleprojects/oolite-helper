"""The heading, location, details, tip and status line."""

from .base import Component
from .style import ACCENT, DIM, FG, GREEN, RED


class Heading(Component):
    """The context in large letters: FLYING, DOCKED, RED ALERT..."""

    def __init__(self, model, style, label):
        self.label = label
        super().__init__(model, style)

    def select(self, model):
        return model.topic("context")

    def draw(self, context):
        colour = RED if context in ("red alert", "ship destroyed") else ACCENT
        self.label.config(text=context.upper(), fg=colour)


class Location(Component):
    """The system you're in, and whether it was your jump target."""

    def __init__(self, model, style, label):
        self.label = label
        super().__init__(model, style)

    def select(self, model):
        return model.topic("location")

    def draw(self, location):
        name, reached, aimed_at = location
        text = name or ""
        if reached:
            text += "  ✓ your jump target"
        elif aimed_at:
            text += f"  (aimed for {aimed_at})"
        self.label.config(text=text, fg=GREEN if reached else (RED if aimed_at else FG))


class Details(Component):
    """Small notes on the right: countdown, autopilot, screen, view, price age."""

    def __init__(self, model, style, label):
        self.label = label
        super().__init__(model, style)

    def select(self, model):
        return (model.topic("details"), model.topic("screen"), model.topic("market_age"))

    def draw(self, value):
        details, (gui, view), market_age = value
        screen = (gui or "-").replace("GUI_SCREEN_", "").replace("_", " ").title()
        view = (view or "-").replace("VIEW_", "").replace("_", " ").title()
        lines = ["    ".join(details), f"Screen: {screen}    View: {view}"]
        if market_age:
            lines.append(f"Market prices: {market_age}")
        self.label.config(text="\n".join(line for line in lines if line))


class Tip(Component):
    """The large tip lines under the tabs."""

    def __init__(self, model, style, label):
        self.label = label
        super().__init__(model, style)

    def select(self, model):
        return model.topic("tip")

    def draw(self, text):
        self.label.config(text=text, pady=self.style.px(8) if text else 0)


def status_line(status):
    """(kind, text) for the status line: an error, a warning, a notice or the last message."""
    if status.get("error"):
        return "error", f"Error (still running): {status['error']}"
    for kind, field in (("warning", "keymap_error"), ("warning", "plugins"), ("notice", "notice")):
        if status.get(field):
            return kind, status[field]
    if status.get("last_message"):
        return "message", status["last_message"]
    return None, ""


class Status(Component):
    """The last message, or an error, along the bottom."""

    def __init__(self, model, style, label):
        self.label = label
        super().__init__(model, style)

    def select(self, model):
        return model.topic("status")

    def draw(self, status):
        self.label.config(text=status_line(status)[1], fg=DIM)
