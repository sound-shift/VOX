"""Start screen — project mode and voice preset."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore, QtWidgets

from app.dsp.presets import PRESETS
from app.dsp.workflows import WORKFLOWS
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
        self.resize(580, 460)
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
        self.mode_combo.addItem("ADR — dub to picture", userData="adr")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)

        layout.addWidget(self._section_label("Voice preset"))
        self.preset_combo = QtWidgets.QComboBox(self)
        for key, preset in PRESETS.items():
            self.preset_combo.addItem(preset.name, userData=key)
        layout.addWidget(self.preset_combo)

        self.hint = QtWidgets.QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 11px;")
        layout.addWidget(self.hint)

        layout.addStretch(1)
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

        self._on_mode_changed()

    def _section_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text.upper())
        label.setObjectName("sectionTitle")
        return label

    def _on_mode_changed(self) -> None:
        mode = self.mode_combo.currentData()
        if mode == "adr":
            idx = self.preset_combo.findData("adr_dialog")
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            self.hint.setText(
                "ADR: File → Import Video для picture lock. Дорожка Dialog — ваш дубляж. "
                "Захватите шум (Capture Noise) на паузе между репликами."
            )
        elif mode == "audiobook":
            self.hint.setText("Audiobook: длинные takes, gate и deverb включены по умолчанию.")
        else:
            self.hint.setText("Podcast: короткие takes. Ctrl+wheel — zoom таймлайна.")

        workflow = WORKFLOWS.get(mode)
        if workflow and mode != "adr":
            idx = self.preset_combo.findData(workflow.preset_key)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)

    def accept(self) -> None:
        self.selection = StartSelection(
            mode=self.mode_combo.currentData(),
            preset_key=self.preset_combo.currentData(),
        )
        super().accept()


__all__ = ["StartScreen", "StartSelection"]
