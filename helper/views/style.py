"""Colours, fonts and sizes shared by every view."""

COLUMN_WIDTH = 600  # px a key panel needs at text scale 1.0
# Layouts: text and spacing scale (multiplied by font_scale) and most key columns.
LAYOUTS = {
    "large": (1.0, 3),
    "compact": (0.6, 6),
}
BG = "#101418"
PANEL = "#171d23"
FG = "#e6e6e6"
ACCENT = "#ffb000"
RED = "#ff4040"
DIM = "#7a8590"
GREEN = "#5fd068"
SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"


class Style:
    """Text and spacing for one window: its layout, scale and width."""

    def __init__(self, width, layout="large", font_scale=1.0):
        layout_scale, max_columns = LAYOUTS[layout]
        self.width = width
        self.scale = layout_scale * font_scale
        self.columns = max(1, min(max_columns, int(width / (COLUMN_WIDTH * self.scale))))
        self.desc_wrap = int(width / self.columns * 0.6)

    def font(self, family, size, *style):
        return (family, max(9, round(size * self.scale)), *style)  # 9: still readable

    def px(self, *sizes):
        """Spacing scaled with the text: one size, or a (before, after) pair."""
        scaled = tuple(round(size * self.scale) for size in sizes)
        return scaled[0] if len(scaled) == 1 else scaled
