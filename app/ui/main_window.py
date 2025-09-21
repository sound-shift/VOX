"""Main application window."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

from app.audio.engine import Recorder, Transport
from app.dsp.presets import get_preset
from app.export.audio import AudioExporter, ExportError
from app.project.database import AutosaveManager, ProjectDatabase
from app.settings.storage import SettingsStorage
from app.timeline.model import Timeline
from app.ui.process_panel import ProcessPanel
from app.ui.timeline_widget import TimelineWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, project_path: Optional[Path], settings: SettingsStorage, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VOX — VoiceOverXeaven")
        self.resize(1200, 720)
        self.timeline = Timeline()
        self.settings = settings
        self.database: Optional[ProjectDatabase] = None
        self.autosaves: Optional[AutosaveManager] = None
        self.project_path = project_path
        if project_path:
            self.database = ProjectDatabase(project_path)
            self.database.initialize()
            self.autosaves = AutosaveManager(project_path, slots=settings.get_option("autosave", "slots", 5))
        self.recorder = Recorder(self.timeline)
        self.transport = Transport(self.timeline)
        self.apply_preset(self.process_panel.state().preset)
        self.exporter = AudioExporter()
        self._build_ui()
        self._create_menus()

    # UI setup
    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(self)
        self.timeline_widget = TimelineWidget(self.timeline, self)
        splitter.addWidget(self.timeline_widget)
        self.process_panel = ProcessPanel(self)
        splitter.addWidget(self.process_panel)
        self.setCentralWidget(splitter)
        self.process_panel.monitorToggled.connect(self._toggle_monitor)
        self.process_panel.bypassToggled.connect(self._toggle_bypass)
        self.process_panel.resetRequested.connect(self._reset_processing)

    def apply_preset(self, preset_key: str) -> None:
        preset = get_preset(preset_key)
        self.process_panel.apply_preset(preset_key, preset)

    def _create_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        self.act_new = file_menu.addAction("New")
        self.act_open = file_menu.addAction("Open…")
        self.act_save = file_menu.addAction("Save")
        self.act_import = file_menu.addAction("Import…")
        self.act_export = file_menu.addAction("Export…")
        self.act_new.triggered.connect(self.new_project)
        self.act_open.triggered.connect(self.open_project)
        self.act_save.triggered.connect(self.save_project)
        self.act_export.triggered.connect(self.export_audio)

        options_menu = bar.addMenu("Options")
        self.act_set_bitrate = options_menu.addAction("MP3 Bitrate…")
        self.act_set_bitrate.triggered.connect(self._choose_bitrate)
        self.act_set_reference = options_menu.addAction("Set Reference File…")
        self.act_set_reference.triggered.connect(self._choose_reference)

    # menu handlers
    def new_project(self) -> None:
        self.timeline = Timeline()
        self.timeline_widget.timeline = self.timeline
        self.timeline_widget.refresh()
        self.recorder = Recorder(self.timeline)
        self.apply_preset(self.process_panel.state().preset)
        self.transport = Transport(self.timeline)

    def open_project(self) -> None:
        if not self.database:
            return
        self.timeline = self.database.load_timeline()
        self.timeline_widget.timeline = self.timeline
        self.timeline_widget.refresh()
        self.recorder = Recorder(self.timeline)

    def save_project(self) -> None:
        if not self.database or not self.project_path:
            return
        audio_dir = self.project_path.parent / "audio"
        self.database.save_timeline(self.timeline, audio_dir)
        if self.autosaves:
            self.autosaves.autosave(self.project_path)

    def export_audio(self) -> None:
        if not self.timeline.tracks:
            QtWidgets.QMessageBox.warning(self, "Export", "No tracks to export")
            return
        track = next(iter(self.timeline.tracks.values()))
        if not track.clips:
            QtWidgets.QMessageBox.warning(self, "Export", "No clips to export")
            return
        take = track.clips[0].active_take()
        if take is None:
            QtWidgets.QMessageBox.warning(self, "Export", "No active take")
            return
        fmt = "wav"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export", filter="Audio (*.wav *.flac *.mp3)")
        if not path:
            return
        suffix = Path(path).suffix.lower().lstrip(".") or fmt
        try:
            result = self.exporter.export(take.data, self.timeline.sample_rate, Path(path), suffix, mp3_bitrate=self.settings.get_option("audio", "mp3_bitrate", 192))
        except ExportError as exc:
            QtWidgets.QMessageBox.critical(self, "Export failed", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self,
            "Export complete",
            f"Saved to {result.path}\nLoudness: {result.report.integrated_lufs:.2f} LUFS\nTrue Peak: {result.report.true_peak:.2f} dBTP",
        )

    def _choose_bitrate(self) -> None:
        bitrate, ok = QtWidgets.QInputDialog.getItem(
            self,
            "MP3 Bitrate",
            "Select bitrate:",
            ["128", "160", "192", "256", "320"],
            2,
            editable=False,
        )
        if ok:
            self.settings.set_option("audio", "mp3_bitrate", int(bitrate))

    def _choose_reference(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select reference file")
        if path:
            self.settings.set_option("processing", "reference_file", path)

    def _toggle_monitor(self, state: bool) -> None:
        for track in self.timeline.tracks.values():
            track.monitor_processed = state

    def _toggle_bypass(self, state: bool) -> None:
        self.recorder.bypass_processing = state

    def _reset_processing(self) -> None:
        preset_key = self.process_panel.state().preset
        preset = get_preset(preset_key)
        self.process_panel.update_from_preset(preset)


__all__ = ["MainWindow"]
