"""The View base class."""


class View:
    """Subclasses define select(model) and draw(value).

    Constructing a view subscribes it, and it draws straight away.
    """

    def __init__(self, model, style):
        self.model = model
        self.style = style
        self.subscription = model.watch(self.select, self.draw)

    def select(self, model):
        raise NotImplementedError

    def draw(self, value):
        raise NotImplementedError

    def dispatch(self, action):
        """Send a "ui/..." action and redraw whatever it changes."""
        self.model.dispatch(action)
        self.model.notify()

    def refresh(self):
        """Redraw after a change to the view's own local state."""
        self.model.notify()

    def close(self):
        self.subscription.cancel()
