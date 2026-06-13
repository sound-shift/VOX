"""Start screen — project mode and voice preset."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore, QtWidgets

from app.dsp.presets import PRESETS
from app.ui import palette


@dataclass
class StartSelection:
    mode: str
    preset_key: str


class StartScreen(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VOX — VoiceOverXeaven")
        self.setModal(True)
        self.resize(560, 420)
        self.selection = StartSelection(mode="podcast", preset_key="male_low")
        self.setStyleSheet(f"background: {palette.BG_DEEP}; color: {palette.TEXT_PRIMARY};")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(18)

        title = QtWidgets.QLabel("VOX")
        title.setStyleSheet(f"font-size: 42px; font-weight: 800; color: {palette.ACCENT_ORANGE}; letter-spacing: 4px;")
        subtitle = QtWidgets.QLabel("VoiceOverXeaven")
        subtitle.setStyleSheet(f"font-size: 14px; color: {palette.TEXT_SECONDARY}; margin-bottom: 8px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._section_label("Workflow"))
        self.mode_combo = QtWidgets.QComboBox(self)
        self.mode_combo.addItem("Podcast — short takes", userData="podcast")
        self.mode_combo.addItem("Audiobook — long takes", userData="audiobook")
        layout.addWidget(self.mode_combo)

        layout.addWidget(self._section_label("Voice preset"))
        self.preset_combo = QtWidgets.QComboBox(self)
        for key, preset in PRESETS.items():
            self.preset_combo.addItem(preset.name, userData=key)
        layout.addWidget(self.preset_combo)

        layout.addStretch(1)
        hint = QtWidgets.QLabel("Tip: arm track → Record. Ctrl+wheel zooms the arrange view.")
        hint.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 11px;")
        layout.addWidget(hint)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        start = QtWidgets.QPushButton("Open Session")
        start.setObjectName("primaryBtn")
        start.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(start)
        layout.addLayout(buttons)

    def _section_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text.upper())
        label.setObjectName("sectionTitle")
        return label

    def accept(self) -> None:
        self.selection = StartSelection(
            mode=self.mode_combo.currentData(),
            preset_key=self.preset_combo.currentData(),
        )
        super().accept()


__all__ = ["StartScreen", "StartSelection"]
