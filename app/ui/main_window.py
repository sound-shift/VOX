"""Main application window — Logic-inspired shell."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.audio.engine import PlaybackEngine, Recorder, Transport
from app.audio.media_io import AUDIO_IMPORT_FILTER, read_audio_mono
from app.dsp.noise_profile import NoiseProfile
from app.dsp.pipeline import ProcessingOptions, process_take
from app.dsp.presets import get_preset
from app.dsp.workflows import get_workflow
from app.export.audio import AudioExporter, ExportError
from app.project.database import AutosaveManager, ProjectDatabase
from app.settings.storage import SettingsStorage
from app.timeline.model import Clip, Timeline
from app.timeline.undo import UndoStack
from app.ui.arrange_view import ArrangeView
from app.ui.options_dialog import OptionsDialog
from app.ui.palette import TRACK_COLORS
from app.ui.process_panel import ProcessPanel
from app.ui.transport_bar import TransportBar
from app.ui.video_panel import VideoPanel
from app.ui.workflow_tips import WorkflowTipsBar
from app.video.session import VideoSession

VIDEO_IMPORT_FILTER = "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*.*)"
REFERENCE_FILTER = "Audio (*.wav *.flac *.mp3 *.ogg *.m4a);;All files (*.*)"


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
        self.setWindowTitle("VOX — VoiceOverXeaven")
        self.resize(1280, 820)
        self.timeline = Timeline()
        self.settings = settings
        self.database: Optional[ProjectDatabase] = None
        self.autosaves: Optional[AutosaveManager] = None
        self.project_path = project_path
        self._current_preset = "male_low"
        self._shortcuts: list[QtGui.QShortcut] = []
        self._playback_origin_sec = 0.0
        self._workflow = get_workflow(mode)
        self._noise_profile: Optional[NoiseProfile] = None
        self.video_session = VideoSession()
        self._undo = UndoStack()
        self._loop_enabled = False
        self._loop_in: Optional[float] = None
        self._loop_out: Optional[float] = None

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
        self._wire_transport()
        self._setup_hotkeys()
        self._setup_autosave()
        self._offer_autosave_recovery()
        self._restore_video_from_project()
        self._restore_noise_profile()
        self._sync_transport_time()
        self._undo.reset(self.timeline)

    def apply_workflow(self, mode: str) -> None:
        self.mode = mode
        self._workflow = get_workflow(mode)
        self.apply_preset(self._workflow.preset_key)
        self.process_panel.apply_workflow(self._workflow)
        labels = {"podcast": "Podcast", "audiobook": "Audiobook", "adr": "ADR"}
        self.setWindowTitle(f"VOX — VoiceOverXeaven ({labels.get(mode, mode)})")
        self.tips_bar.set_mode(mode)
        self.video_panel.set_adr_mode(mode == "adr")
        self._set_status(f"Workflow: {labels.get(mode, mode)}")

    def _build_ui(self) -> None:
        shell = QtWidgets.QWidget(self)
        root = QtWidgets.QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.video_panel = VideoPanel(self)
        self.video_panel.importRequested.connect(self.import_video)
        self.video_panel.seekRequested.connect(self._seek_from_video)
        root.addWidget(self.video_panel)

        self.tips_bar = WorkflowTipsBar(self)
        root.addWidget(self.tips_bar)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.arrange_view = ArrangeView(self.timeline, self)
        self.process_panel = ProcessPanel(self)
        body.addWidget(self.arrange_view, stretch=4)
        body.addWidget(self.process_panel, stretch=0)
        root.addLayout(body, stretch=1)

        self.transport_bar = TransportBar(self)
        root.addWidget(self.transport_bar)
        self.setCentralWidget(shell)

        self.arrange_view.trackSelected.connect(self._on_track_selected)
        self.arrange_view.playheadMoved.connect(self._on_playhead_moved)
        self.arrange_view.armToggled.connect(self._toggle_arm_track)
        self.arrange_view.takeSelected.connect(self._select_take)
        self.process_panel.monitorToggled.connect(self._toggle_monitor)
        self.process_panel.bypassToggled.connect(self._toggle_bypass)
        self.process_panel.resetRequested.connect(self._reset_processing)
        self.process_panel.captureNoiseRequested.connect(self.capture_noise_sample)
        self.process_panel.pictureLockReferenceRequested.connect(self.use_picture_lock_reference)
        self.playback.positionChanged.connect(self._on_playback_position)
        self.playback.finished.connect(self._on_playback_finished)

    def apply_preset(self, preset_key: str) -> None:
        self._current_preset = preset_key
        self.process_panel.apply_preset(preset_key, get_preset(preset_key))

    def _processing_options(self) -> ProcessingOptions:
        state = self.process_panel.processing_state()
        ref = self.settings.get_option("processing", "reference_file")
        ref_path = Path(ref) if ref else None
        return ProcessingOptions(
            preset_key=self._current_preset,
            reference_path=ref_path,
            match_weight=state.match_weight,
            tilt_db_per_oct=state.tilt_db_per_oct,
            isolation_amount=state.isolation_amount,
            dereverb_amount=state.dereverb_amount,
            denoise_reduction_db=state.denoise_db,
            denoise_floor_db=state.denoise_floor_db,
            denoise_sensitivity=state.denoise_sensitivity,
            noise_profile=self._noise_profile,
            use_noise_profile=state.use_noise_profile,
            gate_enable=state.gate_enable,
            bypass=self.recorder.bypass_processing,
            use_ml_isolation=state.use_ml_isolation,
        )

    def _restore_noise_profile(self) -> None:
        payload = self.settings.get_option("processing", "noise_profile")
        profile = NoiseProfile.from_dict(payload if isinstance(payload, dict) else None)
        if profile:
            self._noise_profile = profile
            self.process_panel.set_noise_profile_status(profile.duration_sec)

    def _persist_noise_profile(self) -> None:
        if self._noise_profile:
            self.settings.set_option("processing", "noise_profile", self._noise_profile.to_dict())
        else:
            self.settings.set_option("processing", "noise_profile", None)

    def capture_noise_sample(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Noise print", "Select a track with audio first")
            return
        clip, offset = self._clip_at_playhead(track_id)
        if clip is None:
            QtWidgets.QMessageBox.information(self, "Noise print", "No clip at playhead")
            return
        take = clip.active_take()
        if take is None or not take.data:
            QtWidgets.QMessageBox.information(self, "Noise print", "No audio in clip at playhead")
            return

        sr = self.timeline.sample_rate
        window = 0.5
        center = int(offset * sr)
        half = int(window * sr / 2)
        start = max(0, center - half)
        end = min(len(take.data), center + half)
        segment = take.data[start:end]
        if len(segment) < sr // 20:
            QtWidgets.QMessageBox.warning(
                self,
                "Noise print",
                "Too little audio at playhead — need ~0.05 s of noise",
            )
            return
        try:
            profile = NoiseProfile.capture(segment, sr)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Noise print", str(exc))
            return
        self._noise_profile = profile
        self._persist_noise_profile()
        self.process_panel.set_noise_profile_status(profile.duration_sec)
        self._set_status(f"Noise profile captured ({profile.duration_sec:.2f}s)")

    def _processed_take_data(self, data: list[float]) -> list[float]:
        return process_take(data, self.timeline.sample_rate, self._processing_options()).processed

    def _wire_transport(self) -> None:
        self.transport_bar.playClicked.connect(self.toggle_playback)
        self.transport_bar.stopClicked.connect(self.stop_playback)
        self.transport_bar.recordClicked.connect(self.record_selected_track)
        self.transport_bar.armClicked.connect(self.toggle_arm_selected)
        self.transport_bar.bladeClicked.connect(self.blade_at_cursor)
        self.transport_bar.markerClicked.connect(self.add_marker_at_cursor)
        self.transport_bar.loopInClicked.connect(self.set_loop_in)
        self.transport_bar.loopOutClicked.connect(self.set_loop_out)
        self.transport_bar.loopToggleClicked.connect(self.toggle_loop)
        self.transport_bar.punchClicked.connect(self.punch_record)

    def _undo_push(self) -> None:
        self._undo.push(self.timeline)

    def undo(self) -> None:
        if self._undo.undo(self.timeline):
            self.arrange_view.refresh()
            self._set_status("Undo")

    def redo(self) -> None:
        if self._undo.redo(self.timeline):
            self.arrange_view.refresh()
            self._set_status("Redo")

    def set_loop_in(self) -> None:
        self._loop_in = self.transport.position
        if self._loop_out is not None and self._loop_out <= self._loop_in:
            self._loop_out = None
        self._update_loop_ui()
        self._set_status(f"Loop in @ {self._loop_in:.1f}s")

    def set_loop_out(self) -> None:
        self._loop_out = self.transport.position
        if self._loop_in is not None and self._loop_out <= self._loop_in:
            self._loop_in, self._loop_out = self._loop_out, self._loop_in
        self._update_loop_ui()
        self._set_status(f"Loop out @ {self._loop_out:.1f}s")

    def toggle_loop(self) -> None:
        if self._loop_in is None or self._loop_out is None:
            QtWidgets.QMessageBox.information(self, "Loop", "Set loop in ([) and loop out (]) first")
            self.transport_bar.btn_loop.setChecked(False)
            return
        self._loop_enabled = self.transport_bar.btn_loop.isChecked()
        self._update_loop_ui()
        self._set_status("Loop on" if self._loop_enabled else "Loop off")

    def _update_loop_ui(self) -> None:
        self.arrange_view.set_loop_region(self._loop_in, self._loop_out)
        self.transport_bar.set_loop_region(self._loop_in, self._loop_out)
        self.transport_bar.set_loop_enabled(self._loop_enabled)

    def _seek_from_video(self, seconds: float) -> None:
        self.transport.locate(seconds)
        self.arrange_view.set_playhead(seconds)
        self.video_panel.seek(seconds)
        self._sync_transport_time()

    def _select_take(self, clip_id: int, take_id: int) -> None:
        if self.timeline.set_active_take(clip_id, take_id):
            self._undo_push()
            self.arrange_view.refresh()
            self._set_status(f"Active take #{take_id}")

    def use_picture_lock_reference(self) -> None:
        track = self._ensure_picture_track()
        clip, _ = self._clip_at_playhead(track.id)
        if clip is None and track.clips:
            clip = track.clips[0]
        if clip is None:
            QtWidgets.QMessageBox.information(self, "Match EQ", "Import video first (Picture Lock track)")
            return
        take = clip.active_take()
        if take is None or not take.data:
            QtWidgets.QMessageBox.information(self, "Match EQ", "No audio on Picture Lock track")
            return
        ref_dir = self._project_dir() / ".vox_refs"
        ref_dir.mkdir(exist_ok=True)
        ref_path = ref_dir / "picture_lock_ref.wav"
        from app.audio.engine import write_wav_mono

        write_wav_mono(ref_path, take.data, self.timeline.sample_rate)
        self.settings.set_option("processing", "reference_file", str(ref_path))
        self._set_status(f"Reference from Picture Lock ({len(take.data) / self.timeline.sample_rate:.1f}s)")

    def punch_record(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Punch-in", "Select a track first")
            return
        if not self.timeline.get_track(track_id).armed:
            self.timeline.arm_track(track_id, True)
        if self._loop_in is not None and self._loop_out is not None and self._loop_out > self._loop_in:
            punch_in, punch_out = self._loop_in, self._loop_out
        else:
            punch_in = self.transport.position
            punch_out = punch_in + self._workflow.record_duration_sec
        self.transport.locate(punch_in)
        self._undo_push()
        try:
            self.recorder.punch_record(track_id, punch_in, punch_out, prefer_live=True)
        except RuntimeError as exc:
            QtWidgets.QMessageBox.warning(self, "Punch-in", str(exc))
            return
        self.arrange_view.refresh()
        self._set_status(f"Punch-in {punch_in:.1f}s–{punch_out:.1f}s")

    def show_quick_tour(self) -> None:
        from app.ui.quick_tour import QuickTour

        tour = QuickTour(self)
        tour.exec()

    def _create_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        file_menu.addAction("New", self.new_project, "Ctrl+N")
        file_menu.addAction("Open…", self.open_project, "Ctrl+O")
        file_menu.addAction("Save", self.save_project, "Ctrl+S")
        file_menu.addAction("Save As…", self.save_project_as, "Shift+S")
        file_menu.addAction("Import Audio…", self.import_audio, "Ctrl+I")
        file_menu.addAction("Import Video…", self.import_video)
        file_menu.addAction("Export…", self.export_audio, "Ctrl+E")
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        options_menu = bar.addMenu("Options")
        options_menu.addAction("Preferences…", self.open_preferences)
        options_menu.addAction("MP3 Bitrate…", self._choose_bitrate)
        options_menu.addAction("Capture Noise Print @ Playhead", self.capture_noise_sample)
        options_menu.addAction("Set Reference (Match EQ)…", self._choose_reference)
        options_menu.addAction("Use Picture Lock as Reference", self.use_picture_lock_reference)

        view_menu = bar.addMenu("View")
        view_menu.addAction("Zoom In", lambda: self.arrange_view.set_zoom(12), "Z")
        view_menu.addAction("Zoom Out", lambda: self.arrange_view.set_zoom(-12), "X")
        view_menu.addAction("Quick Tour…", self.show_quick_tour)

    def _setup_hotkeys(self) -> None:
        for shortcut in self._shortcuts:
            shortcut.deleteLater()
        self._shortcuts.clear()
        bindings = self.settings.hotkey_bindings()
        mapping = {
            "play_pause": self.toggle_playback,
            "record_take": self.record_selected_track,
            "arm_track": self.toggle_arm_selected,
            "record_armed": self.record_armed_tracks,
            "blade": self.blade_at_cursor,
            "marker": self.add_marker_at_cursor,
            "toggle_takelanes": self.cycle_take_lane,
            "save": self.save_project,
            "save_as": self.save_project_as,
            "open": self.open_project,
            "new": self.new_project,
            "export": self.export_audio,
            "import": self.import_audio,
            "zoom_in": lambda: self.arrange_view.set_zoom(12),
            "zoom_out": lambda: self.arrange_view.set_zoom(-12),
            "bypass_processing": lambda: self.process_panel.btn_bypass.toggle(),
            "monitor_processed": lambda: self.process_panel.btn_monitor.toggle(),
            "undo": self.undo,
            "redo": self.redo,
            "loop_in": self.set_loop_in,
            "loop_out": self.set_loop_out,
            "toggle_loop": self.toggle_loop,
            "punch_record": self.punch_record,
        }
        for action_name, handler in mapping.items():
            seq_text = bindings.get(action_name)
            if not seq_text:
                continue
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(seq_text), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _setup_autosave(self) -> None:
        if hasattr(self, "_autosave_timer"):
            self._autosave_timer.stop()
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
        self._load_timeline_from_db()

    def _project_dir(self) -> Path:
        if self.project_path:
            return self.project_path.parent
        return Path.cwd()

    def _ensure_picture_track(self):
        for track in self.timeline.tracks.values():
            if track.name == "Picture Lock":
                return track
        return self.timeline.add_track("Picture Lock", TRACK_COLORS[2])

    def _restore_video_from_project(self) -> None:
        if not self.database:
            return
        meta = self.database.load_setting("video_path")
        path_str = meta.get("path") if meta else None
        if path_str and Path(path_str).exists():
            self.video_panel.load(Path(path_str))
            self.video_panel.set_muted(True)
            self.video_session.video_path = Path(path_str)

    def _persist_video_path(self) -> None:
        if not self.database:
            return
        if self.video_session.video_path:
            self.database.save_setting("video_path", {"path": str(self.video_session.video_path)})
        else:
            self.database.save_setting("video_path", {"path": None})

    def _selected_track_id(self) -> Optional[int]:
        track_id = self.arrange_view.selected_track_id
        if track_id is not None and track_id in self.timeline.tracks:
            return track_id
        if self.timeline.tracks:
            return next(iter(self.timeline.tracks))
        return None

    def _on_track_selected(self, track_id: int) -> None:
        track = self.timeline.tracks[track_id]
        self.transport_bar.set_armed(track.armed)
        self._set_status(f"Track: {track.name}")

    def _on_playhead_moved(self, seconds: float) -> None:
        self.transport.locate(seconds)
        self.video_panel.seek(seconds)
        self._sync_transport_time()

    def _on_playback_position(self, seconds: float) -> None:
        absolute = self._playback_origin_sec + seconds
        if (
            self._loop_enabled
            and self._loop_in is not None
            and self._loop_out is not None
            and absolute >= self._loop_out - 0.02
        ):
            self._restart_playback_at(self._loop_in)
            return
        self.arrange_view.set_playhead(absolute)
        self.video_panel.seek(absolute)
        self.transport_bar.set_time(absolute)

    def _restart_playback_at(self, position: float) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            return
        clip, offset = self._clip_at_playhead(track_id)
        if clip is None:
            return
        take = clip.active_take()
        if take is None or not take.data:
            return
        track = self.timeline.get_track(track_id)
        sample_offset = int((position - clip.start) * self.timeline.sample_rate)
        sample_offset = max(0, min(sample_offset, len(take.data) - 1))
        data = take.data[sample_offset:]
        if track.monitor_processed and not self.recorder.bypass_processing:
            data = self._processed_take_data(take.data)[sample_offset:]
        self.playback.stop()
        self._playback_origin_sec = position
        self.transport.locate(position)
        self.arrange_view.set_playhead(position)
        self.video_panel.seek(position)
        self.playback.play_take(data, self.timeline.sample_rate)
        self.video_panel.play()

    def _on_playback_finished(self) -> None:
        self.transport.pause()
        self.video_panel.pause()
        self._set_status("Stopped")

    def _sync_transport_time(self) -> None:
        self.transport_bar.set_time(self.transport.position)
        self.video_panel.seek(self.transport.position)

    def _set_status(self, text: str) -> None:
        self.transport_bar.set_status(text)
        self.statusBar().showMessage(text)

    def _clip_at_playhead(self, track_id: int) -> tuple[Optional[Clip], float]:
        track = self.timeline.get_track(track_id)
        pos = self.transport.position
        for clip in track.clips:
            if clip.start <= pos < clip.end:
                return clip, pos - clip.start
        if track.clips:
            return track.clips[0], 0.0
        return None, 0.0

    def toggle_playback(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Playback", "Add or select a track first")
            return
        track = self.timeline.get_track(track_id)
        clip, offset = self._clip_at_playhead(track_id)
        if clip is None:
            QtWidgets.QMessageBox.information(self, "Playback", "No clips on selected track")
            return
        take = clip.active_take()
        if take is None or not take.data:
            QtWidgets.QMessageBox.information(self, "Playback", "No active take to play")
            return
        sample_offset = int(offset * self.timeline.sample_rate)
        data = take.data[sample_offset:]
        if track.monitor_processed and not self.recorder.bypass_processing:
            data = self._processed_take_data(take.data)[sample_offset:]
        if self.playback.is_playing():
            self.playback.pause()
            self.video_panel.pause()
            self.transport.pause()
            self._set_status("Paused")
        else:
            self._playback_origin_sec = self.transport.position
            self.playback.play_take(data, self.timeline.sample_rate)
            self.video_panel.seek(self.transport.position)
            self.video_panel.play()
            self.transport.play()
            self._set_status("Playing")

    def stop_playback(self) -> None:
        self.playback.stop()
        self.video_panel.stop()
        self.transport.pause()
        self.transport.locate(0.0)
        self.arrange_view.set_playhead(0.0)
        self._sync_transport_time()
        self._set_status("Stopped")

    def toggle_arm_selected(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            return
        self._toggle_arm_track(track_id)

    def _toggle_arm_track(self, track_id: int) -> None:
        track = self.timeline.get_track(track_id)
        self.timeline.arm_track(track_id, not track.armed)
        self.arrange_view.refresh()
        self.transport_bar.set_armed(not track.armed)
        self._set_status(f"{track.name} {'armed' if not track.armed else 'disarmed'}")

    def record_selected_track(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Record", "Select a track first")
            return
        if not self.timeline.get_track(track_id).armed:
            self.timeline.arm_track(track_id, True)
        start = max(self.transport.position, self.recorder.transport_end())
        self.transport.locate(start)
        duration = self._workflow.record_duration_sec
        self._undo_push()
        try:
            result = self.recorder.record(
                track_id, duration=duration, prefer_live=True, start_sec=self.transport.position
            )
        except RuntimeError as exc:
            QtWidgets.QMessageBox.warning(self, "Record", str(exc))
            return
        self.arrange_view.refresh()
        secs = len(result.data) / self.timeline.sample_rate
        self._set_status(f"Recorded {secs:.1f}s on {self.timeline.get_track(track_id).name}")

    def record_armed_tracks(self) -> None:
        armed = [t for t in self.timeline.tracks.values() if t.armed]
        if not armed:
            QtWidgets.QMessageBox.information(self, "Record", "Arm at least one track (R)")
            return
        duration = self._workflow.record_duration_sec
        self._undo_push()
        for track in armed:
            self.recorder.record(track.id, duration=duration, prefer_live=True)
        self.arrange_view.refresh()
        self._set_status(f"Recorded {len(armed)} armed track(s)")

    def cycle_take_lane(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            return
        clip, _ = self._clip_at_playhead(track_id)
        if clip is None:
            return
        take_id = self.timeline.cycle_active_take(clip.id)
        if take_id is None:
            self._set_status("Single take only")
            return
        self.arrange_view.refresh()
        self._set_status(f"Active take #{take_id}")

    def blade_at_cursor(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            return
        track = self.timeline.get_track(track_id)
        if not track.clips:
            QtWidgets.QMessageBox.information(self, "Blade", "No clips to split")
            return
        clip, _ = self._clip_at_playhead(track_id)
        if clip is None:
            return
        position = self.transport.position
        if not (clip.start < position < clip.end):
            position = (clip.start + clip.end) / 2.0
        try:
            self._undo_push()
            self.timeline.blade(clip.id, position)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Blade", str(exc))
            return
        self.arrange_view.refresh()
        self._set_status(f"Split at {position:.2f}s")

    def add_marker_at_cursor(self) -> None:
        marker = self.timeline.add_marker(self.transport.position, f"M{len(self.timeline.markers) + 1}")
        self.arrange_view.refresh()
        self._set_status(f"Marker {marker.name} @ {marker.position:.1f}s")

    def import_audio(self) -> None:
        track_id = self._selected_track_id()
        if track_id is None:
            QtWidgets.QMessageBox.information(self, "Import", "Select a track first")
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import audio", filter=AUDIO_IMPORT_FILTER)
        if not path:
            return
        try:
            data, sr = read_audio_mono(Path(path), self.timeline.sample_rate)
        except (OSError, ValueError, RuntimeError) as exc:
            QtWidgets.QMessageBox.critical(self, "Import failed", str(exc))
            return
        if sr != self.timeline.sample_rate:
            self.timeline.sample_rate = sr
        start = self.transport.position
        duration = len(data) / sr
        self._undo_push()
        clip = self.timeline.add_clip(track_id, start=start, end=start + duration)
        self.timeline.add_take(clip, data=data, start=0.0, end=duration, active=True)
        self.arrange_view.refresh()
        self._set_status(f"Imported {Path(path).name}")

    def import_video(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import video (ADR)", filter=VIDEO_IMPORT_FILTER)
        if not path:
            return
        video_path = Path(path)
        try:
            data, sr = self.video_session.load(video_path, self._project_dir(), self.timeline.sample_rate)
        except (OSError, RuntimeError) as exc:
            QtWidgets.QMessageBox.critical(self, "Video import failed", str(exc))
            return
        self.video_panel.load(video_path)
        self.video_panel.set_muted(True)
        if sr != self.timeline.sample_rate:
            self.timeline.sample_rate = sr
        track = self._ensure_picture_track()
        if track.clips:
            track.clips.clear()
        duration = len(data) / sr
        self._undo_push()
        clip = self.timeline.add_clip(track.id, start=0.0, end=duration)
        self.timeline.add_take(clip, data=data, start=0.0, end=duration, active=True)
        self._persist_video_path()
        self.arrange_view.refresh()
        self._set_status(f"Video loaded: {video_path.name} ({duration:.1f}s)")

    def new_project(self) -> None:
        self.timeline = Timeline()
        self.video_session.clear()
        self.video_panel.clear()
        self._loop_in = None
        self._loop_out = None
        self._loop_enabled = False
        self._update_loop_ui()
        self.arrange_view.timeline = self.timeline
        self.arrange_view.selected_track_id = None
        self.arrange_view.refresh()
        self.recorder = Recorder(self.timeline)
        self.transport = Transport(self.timeline)
        self.transport.locate(0.0)
        self.arrange_view.set_playhead(0.0)
        self._sync_transport_time()
        self._undo.reset(self.timeline)
        self._set_status("New project")

    def open_project(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open project", filter="VOX Project (*.voxproj)")
        if not path:
            return
        self.project_path = Path(path)
        self.database = ProjectDatabase(self.project_path)
        self.database.initialize()
        self.autosaves = AutosaveManager(self.project_path, slots=self.settings.get_option("autosave", "slots", 5))
        self._load_timeline_from_db()

    def _load_timeline_from_db(self) -> None:
        if not self.database:
            return
        self.timeline = self.database.load_timeline()
        self.arrange_view.timeline = self.timeline
        self.arrange_view.selected_track_id = None
        self.arrange_view.refresh()
        self.recorder = Recorder(self.timeline)
        self.transport = Transport(self.timeline)
        self._restore_video_from_project()
        self._undo.reset(self.timeline)
        self._set_status(f"Opened {self.project_path.name}")

    def save_project(self, show_message: bool = True) -> None:
        if not self.database or not self.project_path:
            return
        audio_dir = self.project_path.parent / "audio"
        self.database.save_timeline(self.timeline, audio_dir)
        self._persist_video_path()
        if self.autosaves:
            self.autosaves.autosave(self.project_path)
        if show_message:
            self._set_status(f"Saved {self.project_path.name}")

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
        track = self.timeline.get_track(track_id) if track_id else next(iter(self.timeline.tracks.values()))
        clip, offset = self._clip_at_playhead(track.id)
        if clip is None:
            QtWidgets.QMessageBox.warning(self, "Export", "No clips to export")
            return
        take = clip.active_take()
        if take is None:
            QtWidgets.QMessageBox.warning(self, "Export", "No active take")
            return
        sample_offset = int(offset * self.timeline.sample_rate)
        data = self._processed_take_data(take.data)[sample_offset:]
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

    def open_preferences(self) -> None:
        if OptionsDialog(self.settings, self).exec():
            self._setup_autosave()
            self._setup_hotkeys()
            self._set_status("Preferences saved")

    def _choose_bitrate(self) -> None:
        bitrate, ok = QtWidgets.QInputDialog.getItem(
            self, "MP3 Bitrate", "Select bitrate:", ["128", "160", "192", "256", "320"], 2, editable=False
        )
        if ok:
            self.settings.set_option("audio", "mp3_bitrate", int(bitrate))

    def _choose_reference(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Reference for Match EQ", filter=REFERENCE_FILTER)
        if path:
            self.settings.set_option("processing", "reference_file", path)
            self._set_status(f"Reference: {Path(path).name}")

    def _toggle_monitor(self, state: bool) -> None:
        track_id = self._selected_track_id()
        if track_id is not None:
            self.timeline.get_track(track_id).monitor_processed = state
        else:
            for track in self.timeline.tracks.values():
                track.monitor_processed = state

    def _toggle_bypass(self, state: bool) -> None:
        self.recorder.bypass_processing = state

    def _reset_processing(self) -> None:
        self.process_panel.update_from_preset(get_preset(self._current_preset))


__all__ = ["MainWindow"]
