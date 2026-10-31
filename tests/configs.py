"""Reading a test's config.toml through helper.settings (#135)."""

from helper import settings


def load_widgets(path, plugins=()):
    """Every widget config.toml makes, as settings.WidgetSpecs; SystemExit if it's wrong."""
    return settings.load(path, {name: {} for name in plugins})[0].all_widgets


def load_widgetwindows(path, plugins=()):
    """Its widgetwindows, as settings.WindowSpecs; SystemExit if it's wrong."""
    return settings.load(path, {name: {} for name in plugins})[0].widgetwindows
