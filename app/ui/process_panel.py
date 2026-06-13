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
    match_weight: float = 1.0
    isolation_amount: float = 0.0
    dereverb_amount: float = 0.35
    denoise_db: float = 12.0
    gate_enable: bool = False
    tilt_db_per_oct: float = -1.5


class ProcessPanel(QtWidgets.QWidget):
    monitorToggled = QtCore.Signal(bool)
    bypassToggled = QtCore.Signal(bool)
    resetRequested = QtCore.Signal()
    processingChanged = QtCore.Signal()

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

        eq_group = QtWidgets.QGroupBox("Match EQ")
        eq_layout = QtWidgets.QVBoxLayout(eq_group)
        self.preview = EqPreview(self)
        eq_layout.addWidget(self.preview)
        self.knob_match = Knob("Match", 0.0, 100.0, 1.0, "%", 100.0)
        self.knob_match.setFixedWidth(120)
        eq_layout.addWidget(self.knob_match, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(eq_group)

        iso_group = QtWidgets.QGroupBox("Voice Isolation")
        iso_layout = QtWidgets.QVBoxLayout(iso_group)
        self.knob_isolation = Knob("Isolate", 0.0, 100.0, 1.0, "%", 0.0)
        self.knob_isolation.setFixedWidth(120)
        hint = QtWidgets.QLabel("Pulls voice out of music / foley beds")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 10px;")
        iso_layout.addWidget(self.knob_isolation, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        iso_layout.addWidget(hint)
        layout.addWidget(iso_group)

        proc_group = QtWidgets.QGroupBox("Dynamics & Cleanup")
        proc_layout = QtWidgets.QVBoxLayout(proc_group)
        row = QtWidgets.QHBoxLayout()
        self.knob_tilt = Knob("Tilt", -6.0, 6.0, 0.5, " dB/oct", -1.5)
        self.knob_dereverb = Knob("Deverb", 0.0, 100.0, 1.0, "%", 35.0)
        self.knob_denoise = Knob("Denoise", 0.0, 24.0, 1.0, " dB", 12.0)
        for knob in (self.knob_tilt, self.knob_dereverb, self.knob_denoise):
            knob.setFixedWidth(88)
            row.addWidget(knob)
        proc_layout.addLayout(row)
        self.chk_gate = QtWidgets.QCheckBox("Noise gate")
        proc_layout.addWidget(self.chk_gate)
        layout.addWidget(proc_group)

        out_group = QtWidgets.QGroupBox("Monitor")
        out_layout = QtWidgets.QVBoxLayout(out_group)
        self.btn_monitor = QtWidgets.QPushButton("Monitor Processed")
        self.btn_monitor.setCheckable(True)
        self.btn_bypass = QtWidgets.QPushButton("Bypass FX")
        self.btn_bypass.setCheckable(True)
        self.btn_reset = QtWidgets.QPushButton("Reset Preset")
        out_layout.addWidget(self.btn_monitor)
        out_layout.addWidget(self.btn_bypass)
        out_layout.addWidget(self.btn_reset)
        layout.addWidget(out_group)
        layout.addStretch(1)

        self.btn_monitor.toggled.connect(self.monitorToggled.emit)
        self.btn_bypass.toggled.connect(self.bypassToggled.emit)
        self.btn_reset.clicked.connect(self.resetRequested.emit)
        for knob in (self.knob_match, self.knob_isolation, self.knob_tilt, self.knob_dereverb, self.knob_denoise):
            knob.valueChanged.connect(self._emit_processing_changed)
        self.chk_gate.toggled.connect(self._emit_processing_changed)

    def _emit_processing_changed(self) -> None:
        self.processingChanged.emit()

    def apply_preset(self, preset_key: str, preset: VoicePreset) -> None:
        self._state.preset = preset_key
        self.update_from_preset(preset)

    def update_from_preset(self, preset: VoicePreset) -> None:
        self.knob_tilt.setValue(preset.tilt_db_per_oct)
        self.preview.setParams(
            tilt_db_oct=preset.tilt_db_per_oct,
            bass_fc=preset.low_guard_hz,
            bass_max=max(0.5, preset.low_shelf_gain_db + 1.0),
            weight=self.knob_match.value() / 100.0,
        )

    def processing_state(self) -> ProcessState:
        return ProcessState(
            monitor_processed=self.btn_monitor.isChecked(),
            bypass=self.btn_bypass.isChecked(),
            preset=self._state.preset,
            match_weight=self.knob_match.value() / 100.0,
            isolation_amount=self.knob_isolation.value() / 100.0,
            dereverb_amount=self.knob_dereverb.value() / 100.0,
            denoise_db=self.knob_denoise.value(),
            gate_enable=self.chk_gate.isChecked(),
            tilt_db_per_oct=self.knob_tilt.value(),
        )

    def state(self) -> ProcessState:
        return self.processing_state()

    def set_state(self, state: ProcessState) -> None:
        self._state = state
        self.btn_monitor.setChecked(state.monitor_processed)
        self.btn_bypass.setChecked(state.bypass)
        self.knob_match.setValue(state.match_weight * 100.0)
        self.knob_isolation.setValue(state.isolation_amount * 100.0)
        self.knob_dereverb.setValue(state.dereverb_amount * 100.0)
        self.knob_denoise.setValue(state.denoise_db)
        self.chk_gate.setChecked(state.gate_enable)


__all__ = ["ProcessPanel", "ProcessState"]
