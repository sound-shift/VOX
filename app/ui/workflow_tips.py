"""One-line workflow hints shown under the menu bar."""
from __future__ import annotations

from PySide6 import QtWidgets

from app.ui import palette

TIPS = {
    "podcast": "① Select track  ② Arm (R)  ③ Record (*)  ④ Monitor processed  ⑤ Export",
    "audiobook": "① Arm track  ② Record long take  ③ Blade (B) to edit  ④ L = switch takes",
    "adr": "① Import Video  ② Capture noise @ pause  ③ Arm Dialog  ④ Record while watching picture  ⑤ Export",
}


class WorkflowTipsBar(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {palette.BG_PANEL}; border-bottom: 1px solid {palette.BORDER}; padding: 4px 12px;"
        )
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        self.label = QtWidgets.QLabel(TIPS["podcast"])
        self.label.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.label)

    def set_mode(self, mode: str) -> None:
        self.label.setText(TIPS.get(mode, TIPS["podcast"]))

    def set_message(self, text: str) -> None:
        self.label.setText(text)


__all__ = ["WorkflowTipsBar", "TIPS"]
