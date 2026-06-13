"""VOX global theme."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtGui, QtWidgets

from app.ui import palette
from app.ui.styles import APP_STYLESHEET


class ThemeManager:
    def __init__(self, base_font_point_size: int = 10) -> None:
        self._font_size = base_font_point_size

    def apply(self, app: QtWidgets.QApplication, font_point_size: Optional[int] = None) -> None:
        size = font_point_size if font_point_size is not None else self._font_size
        app.setStyle("Fusion")

        pal = QtGui.QPalette()
        pal.setColor(QtGui.QPalette.Window, palette.qcolor(palette.BG_DEEP))
        pal.setColor(QtGui.QPalette.WindowText, palette.qcolor(palette.TEXT_PRIMARY))
        pal.setColor(QtGui.QPalette.Base, palette.qcolor(palette.BG_PANEL))
        pal.setColor(QtGui.QPalette.AlternateBase, palette.qcolor(palette.BG_RAISED))
        pal.setColor(QtGui.QPalette.Text, palette.qcolor(palette.TEXT_PRIMARY))
        pal.setColor(QtGui.QPalette.Button, palette.qcolor(palette.BG_RAISED))
        pal.setColor(QtGui.QPalette.ButtonText, palette.qcolor(palette.TEXT_PRIMARY))
        pal.setColor(QtGui.QPalette.Highlight, palette.qcolor(palette.ACCENT_BLUE))
        pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#000000"))
        app.setPalette(pal)

        font = QtGui.QFont("Segoe UI", size)
        font.setStyleHint(QtGui.QFont.SansSerif)
        app.setFont(font)
        app.setStyleSheet(APP_STYLESHEET)


__all__ = ["ThemeManager"]
