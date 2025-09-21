"""Expose the original Unify process tab for compatibility."""
from __future__ import annotations

from PySide6 import QtWidgets

from .ui_main import ProcessTab  # type: ignore


class LegacyProcessPanel(ProcessTab):
    """Thin wrapper so existing code can instantiate the legacy process panel."""

    def __init__(self, state, shared_state, parent: QtWidgets.QWidget | None = None):
        super().__init__(state, shared_state, parent)


__all__ = ["LegacyProcessPanel"]
