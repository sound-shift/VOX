"""Channel strip / processing inspector."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.dsp.presets import VoicePreset
from app.dsp.workflows import WorkflowConfig
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
    denoise_floor_db: float = -36.0
    denoise_sensitivity: float = 0.5
    use_noise_profile: bool = True
    gate_enable: bool = False
    tilt_db_per_oct: float = -1.5
    use_ml_isolation: bool = False


class ProcessPanel(QtWidgets.QWidget):
    monitorToggled = QtCore.Signal(bool)
    bypassToggled = QtCore.Signal(bool)
    resetRequested = QtCore.Signal()
    processingChanged = QtCore.Signal()
    captureNoiseRequested = QtCore.Signal()
    pictureLockReferenceRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = ProcessState()
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setStyleSheet(f"background: {palette.BG_PANEL}; border-left: 1px solid {palette.BORDER};")
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("CHANNEL STRIP")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        eq_group = QtWidgets.QGroupBox("Match EQ")
        eq_layout = QtWidgets.QVBoxLayout(eq_group)
        self.preview = EqPreview(body)
        eq_layout.addWidget(self.preview)
        self.knob_match = Knob("Match", 0.0, 100.0, 1.0, "%", 100.0)
        self.knob_match.setFixedWidth(120)
        eq_layout.addWidget(self.knob_match, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.btn_picture_ref = QtWidgets.QPushButton("Use Picture Lock as Reference")
        self.btn_picture_ref.setToolTip("ADR: match dialog EQ to on-screen audio")
        eq_layout.addWidget(self.btn_picture_ref)
        layout.addWidget(eq_group)

        noise_group = QtWidgets.QGroupBox("Noise Print")
        noise_layout = QtWidgets.QVBoxLayout(noise_group)
        self.lbl_noise = QtWidgets.QLabel("No profile captured")
        self.lbl_noise.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 10px;")
        self.lbl_noise.setWordWrap(True)
        noise_layout.addWidget(self.lbl_noise)
        self.btn_capture_noise = QtWidgets.QPushButton("Capture @ Playhead")
        self.btn_capture_noise.setToolTip("Move playhead to a noise-only moment (0.5 s), then capture")
        noise_layout.addWidget(self.btn_capture_noise)
        self.chk_use_profile = QtWidgets.QCheckBox("Use noise profile")
        self.chk_use_profile.setChecked(True)
        noise_layout.addWidget(self.chk_use_profile)
        row_noise = QtWidgets.QHBoxLayout()
        self.knob_denoise = Knob("Reduce", 0.0, 24.0, 1.0, " dB", 12.0)
        self.knob_floor = Knob("Floor", -60.0, -20.0, 1.0, " dB", -42.0)
        self.knob_sensitivity = Knob("Sens", 0.0, 100.0, 1.0, "%", 50.0)
        for knob in (self.knob_denoise, self.knob_floor, self.knob_sensitivity):
            knob.setFixedWidth(88)
            row_noise.addWidget(knob)
        noise_layout.addLayout(row_noise)
        layout.addWidget(noise_group)

        iso_group = QtWidgets.QGroupBox("Voice Isolation")
        iso_layout = QtWidgets.QVBoxLayout(iso_group)
        self.knob_isolation = Knob("Isolate", 0.0, 100.0, 1.0, "%", 0.0)
        self.knob_isolation.setFixedWidth(120)
        iso_layout.addWidget(self.knob_isolation, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        from app.dsp.ml_separation import demucs_available, demucs_status_message

        self.chk_ml = QtWidgets.QCheckBox("ML separation (Demucs)")
        self.chk_ml.setToolTip(demucs_status_message())
        self.chk_ml.setEnabled(demucs_available())
        if not demucs_available():
            self.chk_ml.setText("ML (install requirements-ml.txt)")
        iso_layout.addWidget(self.chk_ml)
        layout.addWidget(iso_group)

        proc_group = QtWidgets.QGroupBox("Dynamics")
        proc_layout = QtWidgets.QVBoxLayout(proc_group)
        row = QtWidgets.QHBoxLayout()
        self.knob_tilt = Knob("Tilt", -6.0, 6.0, 0.5, " dB/oct", -1.5)
        self.knob_dereverb = Knob("Deverb", 0.0, 100.0, 1.0, "%", 35.0)
        for knob in (self.knob_tilt, self.knob_dereverb):
            knob.setFixedWidth(120)
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

        scroll.setWidget(body)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.btn_monitor.toggled.connect(self.monitorToggled.emit)
        self.btn_bypass.toggled.connect(self.bypassToggled.emit)
        self.btn_reset.clicked.connect(self.resetRequested.emit)
        self.btn_capture_noise.clicked.connect(self.captureNoiseRequested.emit)
        self.btn_picture_ref.clicked.connect(self.pictureLockReferenceRequested.emit)
        for knob in (
            self.knob_match,
            self.knob_isolation,
            self.knob_tilt,
            self.knob_dereverb,
            self.knob_denoise,
            self.knob_floor,
            self.knob_sensitivity,
        ):
            knob.valueChanged.connect(self._emit_processing_changed)
        self.chk_gate.toggled.connect(self._emit_processing_changed)
        self.chk_use_profile.toggled.connect(self._emit_processing_changed)
        self.chk_ml.toggled.connect(self._emit_processing_changed)

    def _emit_processing_changed(self) -> None:
        self.processingChanged.emit()

    def apply_workflow(self, workflow: WorkflowConfig) -> None:
        idx_preset = workflow.preset_key
        self._state.preset = idx_preset
        self.knob_match.setValue(workflow.match_weight * 100.0)
        self.knob_isolation.setValue(workflow.isolation_amount * 100.0)
        self.knob_dereverb.setValue(workflow.dereverb_amount * 100.0)
        self.knob_denoise.setValue(workflow.denoise_db)
        self.knob_floor.setValue(workflow.denoise_floor_db)
        self.knob_sensitivity.setValue(workflow.denoise_sensitivity * 100.0)
        self.chk_gate.setChecked(workflow.gate_enable)
        if workflow.tilt_db_per_oct is not None:
            self.knob_tilt.setValue(workflow.tilt_db_per_oct)

    def apply_preset(self, preset_key: str, preset: VoicePreset) -> None:
        self._state.preset = preset_key
        self.update_from_preset(preset)

    def update_from_preset(self, preset: VoicePreset) -> None:
        if abs(self.knob_tilt.value() - preset.tilt_db_per_oct) > 0.01:
            self.knob_tilt.setValue(preset.tilt_db_per_oct)
        self.preview.setParams(
            tilt_db_oct=preset.tilt_db_per_oct,
            bass_fc=preset.low_guard_hz,
            bass_max=max(0.5, preset.low_shelf_gain_db + 1.0),
            weight=self.knob_match.value() / 100.0,
        )

    def set_noise_profile_status(self, duration_sec: Optional[float]) -> None:
        if duration_sec is None:
            self.lbl_noise.setText("No profile captured")
            self.lbl_noise.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 10px;")
        else:
            self.lbl_noise.setText(f"Profile OK — {duration_sec:.2f}s captured")
            self.lbl_noise.setStyleSheet(f"color: {palette.ACCENT_PLAY}; font-size: 10px;")

    def processing_state(self) -> ProcessState:
        return ProcessState(
            monitor_processed=self.btn_monitor.isChecked(),
            bypass=self.btn_bypass.isChecked(),
            preset=self._state.preset,
            match_weight=self.knob_match.value() / 100.0,
            isolation_amount=self.knob_isolation.value() / 100.0,
            dereverb_amount=self.knob_dereverb.value() / 100.0,
            denoise_db=self.knob_denoise.value(),
            denoise_floor_db=self.knob_floor.value(),
            denoise_sensitivity=self.knob_sensitivity.value() / 100.0,
            use_noise_profile=self.chk_use_profile.isChecked(),
            gate_enable=self.chk_gate.isChecked(),
            tilt_db_per_oct=self.knob_tilt.value(),
            use_ml_isolation=self.chk_ml.isChecked() and self.chk_ml.isEnabled(),
        )

    def state(self) -> ProcessState:
        return self.processing_state()


__all__ = ["ProcessPanel", "ProcessState"]
