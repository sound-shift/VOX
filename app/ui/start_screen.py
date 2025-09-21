"""Start screen for selecting project mode and preset."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtWidgets

from app.dsp.presets import PRESETS


@dataclass
class StartSelection:
    mode: str
    preset_key: str


class StartScreen(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VoiceOverXeaven")
        self.setModal(True)
        self.selection = StartSelection(mode="podcast", preset_key="male_low")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Choose workflow:"))
        self.mode_combo = QtWidgets.QComboBox(self)
        self.mode_combo.addItem("Podcast", userData="podcast")
        self.mode_combo.addItem("Audiobook", userData="audiobook")
        layout.addWidget(self.mode_combo)

        layout.addWidget(QtWidgets.QLabel("Voice preset:"))
        self.preset_combo = QtWidgets.QComboBox(self)
        for key, preset in PRESETS.items():
            self.preset_combo.addItem(preset.name, userData=key)
        layout.addWidget(self.preset_combo)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.selection = StartSelection(
            mode=self.mode_combo.currentData(),
            preset_key=self.preset_combo.currentData(),
        )
        super().accept()


__all__ = ["StartScreen", "StartSelection"]
