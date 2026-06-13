"""Main application window."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.audio.engine import PlaybackEngine, Recorder, Transport, read_wav_mono
from app.dsp.magic import process_magic
from app.dsp.presets import get_preset
from app.export.audio import AudioExporter, ExportError
from app.project.database import AutosaveManager, ProjectDatabase
from app.settings.storage import SettingsStorage
from app.timeline.model import Timeline
from app.ui.process_panel import ProcessPanel
from app.ui.timeline_widget import TimelineWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        project_path: Optional[Path],
        settings: SettingsStorage,
        mode: str = "podcast",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle(f"VOX — VoiceOverXeaven ({mode})")
        self.resize(1200, 720)
        self.timeline = Timeline()
        self.settings = settings
        self.database: Optional[ProjectDatabase] = None
        self.autosaves: Optional[AutosaveManager] = None
        self.project_path = project_path
        self._current_preset = "male_low"
        if project_path:
            self.database = ProjectDatabase(project_path)
            self.database.initialize()
            self.autosaves = AutosaveManager(project_path, slots=settings.get_option("autosave", "slots", 5))
        self.recorder = Recorder(self.timeline)
        self.transport = Transport(self.timeline)
        self.playback = PlaybackEngine(self)
        self.exporter = AudioExporter()
        self._build_ui()
        self._create_menus()
        self._create_toolbar()
        self._setup_hotkeys()
        self._setup_autosave()
        self._offer_autosave_recovery()
        self.statusBar().showMessage("Ready")

    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(self)
        self.timeline_widget = TimelineWidget(self.timeline, self)
        splitter.addWidget(self.timeline_widget)
        self.process_panel = ProcessPanel(self)
        splitter.addWidget(self.process_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.timeline_widget.trackSelected.connect(self._on_track_selected)
        self.process_panel.monitorToggled.connect(self._toggle_monitor)
        self.process_panel.bypassToggled.connect(self._toggle_bypass)
        self.process_panel.resetRequested.connect(self._reset_processing)

    def apply_preset(self, preset_key: str) -> None:
        self._current_preset = preset_key
        preset = get_preset(preset_key)
        self.process_panel.apply_preset(preset_key, preset)

    def _create_toolbar(self) -> None:
        bar = self.addToolBar("Transport")
        bar.setMovable(False)
        self.btn_play = bar.addAction("Play/Pause")
        self.btn_play.triggered.connect(self.toggle_playback)
        self.btn_record = bar.addAction("Record")
        self.btn_record.triggered.connect(self.record_selected_track)
        self.btn_arm = bar.addAction("Arm")
        self.btn_arm.triggered.connect(self.toggle_arm_selected)
        self.btn_blade = bar.addAction("Blade")
        self.btn_blade.triggered.connect(self.blade_at_cursor)
        self.btn_marker = bar.addAction("Marker")
        self.btn_marker.triggered.connect(self.add_marker_at_cursor)

    def _create_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        self.act_new = file_menu.addAction("New")
        self.act_open = file_menu.addAction("Open…")
        self.act_save = file_menu.addAction("Save")
        self.act_save_as = file_menu.addAction("Save As…")
        self.act_import = file_menu.addAction("Import…")
        self.act_export = file_menu.addAction("Export…")
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        self.act_new.triggered.connect(self.new_project)
        self.act_open.triggered.connect(self.open_project)
        self.act_save.triggered.connect(self.save_project)
        self.act_save_as.triggered.connect(self.save_project_as)
        self.act_import.triggered.connect(self.import_audio)
        self.act_export.triggered.connect(self.export_audio)

        options_menu = bar.addMenu("Options")
        self.act_set_bitrate = options_menu.addAction("MP3 Bitrate…")
        self.act_set_bitrate.triggered.connect(self._choose_bitrate)
        self.act_set_reference = options_menu.addAction("Set Reference File…")
        self.act_set_reference.triggered.connect(self._choose_reference)

    def _setup_hotkeys(self) -> None:
        bindings = self.settings.hotkey_bindings()
        self._hotkey_actions: dict[str, QtGui.QAction] = {}
        mapping = {
            "play_pause": self.toggle_playback,
            "record_take": self.record_selected_track,
            "arm_track": self.toggle_arm_selected,
            "record_armed": self.record_armed_tracks,
            "blade": self.blade_at_cursor,
            "marker": self.add_marker_at_cursor,
            "save": self.save_project,
            "save_as": self.save_project_as,
            "open": self.open_project,
            "new": self.new_project,
            "export": self.export_audio,
            "import": self.import_audio,
            "bypass_processing": lambda: self.process_panel.btn_bypass.toggle(),
            "monitor_processed": lambda: self.process_panel.btn_monitor.toggle(),
        }
        for action_name, handler in mapping.items():
            seq_text = bindings.get(action_name)
            if not seq_text:
                continue
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(seq_text), self)
            shortcut.activated.connect(handler)
            self._hotkey_actions[action_name] = shortcut  # type: ignore[assignment]

    def _setup_autosave(self) -> None:
        interval_sec = int(self.settings.get_option("autosave", "interval_sec", 300))
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setInterval(max(30, interval_sec) * 1000)
        self._autosave_timer.timeout.connect(self._autosave_tick)
        self._autosave_timer.start()

    def _autosave_tick(self) -> None:
        if self.project_path and self.database:
            self.save_project(show_message=False)

    def _offer_autosave_recovery(self) -> None:
        if not self.autosaves:
            return
        candidates = list(self.autosaves.available())
        if not candidates:
            return
        latest = candidates[-1]
        answer = QtWidgets.QMessageBox.question(
            self,
            "Restore autosave",
            f"Found autosave:\n{latest.name}\n\nRestore it?",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.project_path = latest
        self.database = ProjectDatabase(latest)
        self.open_project()

    def _selected_track_id(self) -> Optional[int]:
        track_id = self.timeline_widget.selected_track_id
        if track_id is not None and track_id in self.timeline.tracks:
            return track_id
        if self.timeline.tracks:
            return next(iter(self.timeline.tracks))
        return None

    def _on_track_selected(self, track_id: int) -> None:
        self.statusBar().showMessage(f"Selected track: {self.timeline.tracks[track_id].name}")

    def _processed_take_data(self, data: list[float]) -> list[float]:
        if self.recorder.bypass_processing:
            return list(data)
        result = process_magic(data, self.timeline.sample_rate, self._current_preset)
        return result.processed

    def toggle_playback(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Playback", "Add or select a track first")
            return
        track = self.timeline.get_track(track_id)
        if not track.clips:
            QtWidgets.QMessageBox.information(self, "Playback", "No clips on selected track")
            return
        take = track.clips[0].active_take()
        if take is None or not take.data:
            QtWidgets.QMessageBox.information(self, "Playback", "No active take to play")
            return
        data = take.data
        if track.monitor_processed and not self.recorder.bypass_processing:
            data = self._processed_take_data(take.data)
        if self.playback.is_playing():
            self.playback.pause()
            self.transport.pause()
        else:
            self.playback.play_take(data, self.timeline.sample_rate)
            self.transport.play()
        self.statusBar().showMessage("Playing" if self.transport.playing else "Paused")

    def toggle_arm_selected(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            return
        track = self.timeline.get_track(track_id)
        self.timeline.arm_track(track_id, not track.armed)
        self.timeline_widget.refresh()
        state = "armed" if not track.armed else "disarmed"
        self.statusBar().showMessage(f"Track {track.name} {state}")

    def record_selected_track(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Record", "Select a track first")
            return
        track = self.timeline.get_track(track_id)
        if not track.armed:
            self.timeline.arm_track(track_id, True)
        duration = 5.0 if self.mode == "podcast" else 8.0
        try:
            result = self.recorder.record(track_id, duration=duration)
        except RuntimeError as exc:
            QtWidgets.QMessageBox.warning(self, "Record", str(exc))
            return
        self.timeline_widget.refresh()
        self.statusBar().showMessage(f"Recorded take on {track.name} ({len(result.data) / self.timeline.sample_rate:.1f}s)")

    def record_armed_tracks(self) -> None:
        armed = [track for track in self.timeline.tracks.values() if track.armed]
        if not armed:
            QtWidgets.QMessageBox.information(self, "Record", "Arm at least one track (R)")
            return
        for track in armed:
            duration = 5.0 if self.mode == "podcast" else 8.0
            self.recorder.record(track.id, duration=duration)
        self.timeline_widget.refresh()
        self.statusBar().showMessage(f"Recorded {len(armed)} armed track(s)")

    def blade_at_cursor(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            return
        track = self.timeline.get_track(track_id)
        if not track.clips:
            QtWidgets.QMessageBox.information(self, "Blade", "No clips to split")
            return
        clip = track.clips[0]
        position = self.transport.position or (clip.start + clip.end) / 2.0
        try:
            self.timeline.blade(clip.id, position)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Blade", str(exc))
            return
        self.timeline_widget.refresh()
        self.statusBar().showMessage(f"Split clip at {position:.2f}s")

    def add_marker_at_cursor(self) -> None:
        position = self.transport.position
        marker = self.timeline.add_marker(position, f"M{len(self.timeline.markers) + 1}")
        self.statusBar().showMessage(f"Marker {marker.name} at {marker.position:.2f}s")

    def import_audio(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Import", "Select a track first")
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import audio", filter="Audio (*.wav)")
        if not path:
            return
        try:
            data, sr = read_wav_mono(Path(path), self.timeline.sample_rate)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.critical(self, "Import failed", str(exc))
            return
        if sr != self.timeline.sample_rate:
            self.timeline.sample_rate = sr
        duration = len(data) / sr
        clip = self.timeline.add_clip(track_id, start=0.0, end=duration)
        self.timeline.add_take(clip, data=data, start=0.0, end=duration, active=True)
        self.timeline_widget.refresh()
        self.statusBar().showMessage(f"Imported {Path(path).name} ({duration:.1f}s)")

    def new_project(self) -> None:
        self.timeline = Timeline()
        self.timeline_widget.timeline = self.timeline
        self.timeline_widget.selected_track_id = None
        self.timeline_widget.refresh()
        self.recorder = Recorder(self.timeline)
        self.transport = Transport(self.timeline)
        self.statusBar().showMessage("New project")

    def open_project(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open project", filter="VOX Project (*.voxproj)")
        if path:
            self.project_path = Path(path)
            self.database = ProjectDatabase(self.project_path)
            self.database.initialize()
            self.autosaves = AutosaveManager(self.project_path, slots=self.settings.get_option("autosave", "slots", 5))
        if not self.database:
            return
        self.timeline = self.database.load_timeline()
        self.timeline_widget.timeline = self.timeline
        self.timeline_widget.selected_track_id = None
        self.timeline_widget.refresh()
        self.recorder = Recorder(self.timeline)
        self.transport = Transport(self.timeline)
        self.statusBar().showMessage(f"Opened {self.project_path}")

    def save_project(self, show_message: bool = True) -> None:
        if not self.database or not self.project_path:
            return
        audio_dir = self.project_path.parent / "audio"
        self.database.save_timeline(self.timeline, audio_dir)
        if self.autosaves:
            self.autosaves.autosave(self.project_path)
        if show_message:
            self.statusBar().showMessage(f"Saved {self.project_path.name}")

    def save_project_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save project as", filter="VOX Project (*.voxproj)")
        if not path:
            return
        if not path.endswith(".voxproj"):
            path += ".voxproj"
        self.project_path = Path(path)
        self.database = ProjectDatabase(self.project_path)
        self.database.initialize()
        self.autosaves = AutosaveManager(self.project_path, slots=self.settings.get_option("autosave", "slots", 5))
        self.save_project()

    def export_audio(self) -> None:
        if not self.timeline.tracks:
            QtWidgets.QMessageBox.warning(self, "Export", "No tracks to export")
            return
        track_id = self._selected_track_id()
        track = self.timeline.get_track(track_id) if track_id is not None else next(iter(self.timeline.tracks.values()))
        if not track.clips:
            QtWidgets.QMessageBox.warning(self, "Export", "No clips to export")
            return
        take = track.clips[0].active_take()
        if take is None:
            QtWidgets.QMessageBox.warning(self, "Export", "No active take")
            return
        data = self._processed_take_data(take.data)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export", filter="Audio (*.wav *.flac *.mp3)")
        if not path:
            return
        suffix = Path(path).suffix.lower().lstrip(".") or "wav"
        try:
            result = self.exporter.export(
                data,
                self.timeline.sample_rate,
                Path(path),
                suffix,
                mp3_bitrate=self.settings.get_option("audio", "mp3_bitrate", 192),
            )
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
        preset = get_preset(self._current_preset)
        self.process_panel.update_from_preset(preset)


__all__ = ["MainWindow"]
