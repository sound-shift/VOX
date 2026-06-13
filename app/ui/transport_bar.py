"""Bottom transport bar — Logic-inspired layout."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui import palette


class TransportBar(QtWidgets.QFrame):
    playClicked = QtCore.Signal()
    stopClicked = QtCore.Signal()
    recordClicked = QtCore.Signal()
    armClicked = QtCore.Signal()
    bladeClicked = QtCore.Signal()
    markerClicked = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("transportBar")
        self.setFixedHeight(72)
        self.setStyleSheet(
            f"""
            QFrame#transportBar {{
                background: {palette.BG_TRANSPORT};
                border-top: 1px solid {palette.BORDER};
            }}
            """
        )
        self._time_label = QtWidgets.QLabel("00:00.0")
        self._time_label.setStyleSheet(f"color: {palette.ACCENT_ORANGE}; font-size: 18px; font-weight: 700; font-family: 'Consolas', monospace;")
        self._status = QtWidgets.QLabel("Ready")
        self._status.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 11px;")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        layout.addWidget(self._time_label)
        layout.addStretch(1)

        center = QtWidgets.QHBoxLayout()
        center.setSpacing(8)
        self.btn_stop = self._make_btn("■", "Stop", palette.BG_RAISED)
        self.btn_play = self._make_btn("▶", "Play / Pause", palette.ACCENT_PLAY, dark_text=True)
        self.btn_record = self._make_btn("●", "Record", palette.ACCENT_RECORD)
        self.btn_arm = self._make_btn("R", "Arm track", palette.BG_RAISED, checkable=True)
        self.btn_blade = self._make_btn("⌇", "Blade", palette.BG_RAISED)
        self.btn_marker = self._make_btn("M", "Marker", palette.BG_RAISED)
        for btn in (self.btn_stop, self.btn_play, self.btn_record, self.btn_arm, self.btn_blade, self.btn_marker):
            center.addWidget(btn)
        layout.addLayout(center)
        layout.addStretch(1)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self._status)
        layout.addLayout(right)

        self.btn_play.clicked.connect(self.playClicked.emit)
        self.btn_stop.clicked.connect(self.stopClicked.emit)
        self.btn_record.clicked.connect(self.recordClicked.emit)
        self.btn_arm.clicked.connect(self.armClicked.emit)
        self.btn_blade.clicked.connect(self.bladeClicked.emit)
        self.btn_marker.clicked.connect(self.markerClicked.emit)

    def _make_btn(self, text: str, tooltip: str, color: str, *, dark_text: bool = False, checkable: bool = False) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setFixedSize(44, 44)
        fg = "#111" if dark_text or color in {palette.ACCENT_PLAY, palette.ACCENT_ARM} else palette.TEXT_PRIMARY
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {color};
                color: {fg};
                border: none;
                border-radius: 22px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
            QPushButton:checked {{ background: {palette.ACCENT_ARM}; color: #111; }}
            """
        )
        return btn

    def set_time(self, seconds: float) -> None:
        mins = int(seconds // 60)
        secs = seconds % 60
        self._time_label.setText(f"{mins:02d}:{secs:04.1f}")

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_armed(self, armed: bool) -> None:
        self.btn_arm.setChecked(armed)


__all__ = ["TransportBar"]
