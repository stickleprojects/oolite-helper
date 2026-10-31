"""Colour helpers shared by every platform."""


def _lightness(colour):
    r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def readable(text, background):
    """text, or black or white if it's too close to background to read."""
    if text and abs(_lightness(text) - _lightness(background)) > 0.4:
        return text
    return "#000000" if _lightness(background) > 0.5 else "#ffffff"
