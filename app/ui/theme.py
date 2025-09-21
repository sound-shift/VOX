"""VOX UI theme derived from the original Unify theme."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from app.legacy.unify import ui_theme as legacy_theme


class ThemeManager:
    """Apply and maintain the global dark theme used across the application."""

    def __init__(self, base_font_point_size: int = 10) -> None:
        self._font_size = base_font_point_size

    @property
    def font_size(self) -> int:
        return self._font_size

    def apply(self, app: QtWidgets.QApplication, font_point_size: Optional[int] = None) -> None:
        """Apply the Unify dark theme to *app* and optionally override the font size."""
        size = font_point_size if font_point_size is not None else self._font_size
        legacy_theme.apply_dark_theme(app, base_font_point_size=size)
        self._font_size = size


__all__ = ["ThemeManager"]
