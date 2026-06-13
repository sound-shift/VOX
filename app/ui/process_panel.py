"""Channel strip / processing inspector."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore, QtWidgets

from app.dsp.presets import VoicePreset
from app.legacy.unify.controls import EqPreview, Knob
from app.ui import palette


@dataclass
class ProcessState:
    monitor_processed: bool = False
    bypass: bool = False
    preset: str = "male_low"


class ProcessPanel(QtWidgets.QWidget):
    monitorToggled = QtCore.Signal(bool)
    bypassToggled = QtCore.Signal(bool)
    resetRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = ProcessState()
        self.setMinimumWidth(280)
        self.setMaximumWidth(340)
        self.setStyleSheet(f"background: {palette.BG_PANEL}; border-left: 1px solid {palette.BORDER};")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("CHANNEL STRIP")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        eq_group = QtWidgets.QGroupBox("EQ Preview")
        eq_layout = QtWidgets.QVBoxLayout(eq_group)
        self.preview = EqPreview(self)
        eq_layout.addWidget(self.preview)
        layout.addWidget(eq_group)

        proc_group = QtWidgets.QGroupBox("Processing")
        proc_layout = QtWidgets.QVBoxLayout(proc_group)
        knob_row = QtWidgets.QHBoxLayout()
        self.knob_tilt = Knob("Tilt", -6.0, 6.0, 0.5, " dB/oct", -1.5)
        self.knob_presence = Knob("Presence", 0.0, 6.0, 0.5, " dB", 3.0)
        self.knob_denoise = Knob("Denoise", 0.0, 1.0, 0.1, "", 0.3)
        for knob in (self.knob_tilt, self.knob_presence, self.knob_denoise):
            knob.setFixedWidth(88)
            knob_row.addWidget(knob)
        proc_layout.addLayout(knob_row)

        btn_row = QtWidgets.QVBoxLayout()
        self.btn_monitor = QtWidgets.QPushButton("Monitor Processed")
        self.btn_monitor.setCheckable(True)
        self.btn_bypass = QtWidgets.QPushButton("Bypass FX")
        self.btn_bypass.setCheckable(True)
        self.btn_reset = QtWidgets.QPushButton("Reset Preset")
        btn_row.addWidget(self.btn_monitor)
        btn_row.addWidget(self.btn_bypass)
        btn_row.addWidget(self.btn_reset)
        proc_layout.addLayout(btn_row)
        layout.addWidget(proc_group)
        layout.addStretch(1)

        self.btn_monitor.toggled.connect(self.monitorToggled.emit)
        self.btn_bypass.toggled.connect(self.bypassToggled.emit)
        self.btn_reset.clicked.connect(self.resetRequested.emit)

    def apply_preset(self, preset_key: str, preset: VoicePreset) -> None:
        self._state.preset = preset_key
        self.update_from_preset(preset)

    def update_from_preset(self, preset: VoicePreset) -> None:
        self.knob_tilt.setValue(preset.tilt_db_per_oct)
        self.knob_presence.setValue(preset.presence_gain_db)
        self.preview.setParams(
            tilt_db_oct=preset.tilt_db_per_oct,
            bass_fc=preset.low_guard_hz,
            bass_max=max(0.5, preset.low_shelf_gain_db + 1.0),
            weight=0.8,
        )

    def set_state(self, state: ProcessState) -> None:
        self._state = state
        self.btn_monitor.setChecked(state.monitor_processed)
        self.btn_bypass.setChecked(state.bypass)
        self._state.preset = state.preset

    def state(self) -> ProcessState:
        return ProcessState(
            monitor_processed=self.btn_monitor.isChecked(),
            bypass=self.btn_bypass.isChecked(),
            preset=self._state.preset,
        )


__all__ = ["ProcessPanel", "ProcessState"]
