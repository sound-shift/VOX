"""VOX color palette — Logic Pro inspired, not a clone."""
from __future__ import annotations

from PySide6 import QtGui

# Surfaces
BG_DEEP = "#0e0e10"
BG_PANEL = "#161618"
BG_RAISED = "#1e1e22"
BG_TRACK = "#1a1a1e"
BG_HEADER = "#222226"
BG_TRANSPORT = "#0a0a0c"

# Lines & grid
GRID_MAJOR = "#2e2e34"
GRID_MINOR = "#242428"
BORDER = "#333338"
BORDER_LIGHT = "#44444c"

# Accents
ACCENT_ORANGE = "#ff7043"
ACCENT_RECORD = "#ff3b30"
ACCENT_PLAY = "#34c759"
ACCENT_BLUE = "#5ac8fa"
ACCENT_VIOLET = "#bf5af2"
ACCENT_ARM = "#ff9f0a"

# Text
TEXT_PRIMARY = "#f2f2f7"
TEXT_SECONDARY = "#98989f"
TEXT_DIM = "#636366"

# Waveforms
WAVE_FILL = "#4a7cff"
WAVE_FILL_DIM = "#3a5fbf"
WAVE_ARMED = "#ff9f0a"

TRACK_COLORS = ("#5ac8fa", "#34c759", "#ff9f0a", "#bf5af2", "#ff6482", "#64d2ff")


def qcolor(hex_color: str) -> QtGui.QColor:
    return QtGui.QColor(hex_color)
