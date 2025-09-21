#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AudioUnify.py — GUI for UnifyAudio (PySide6)
r9.4.4
- Edit:
  • Фикс курсора: ставится по клику и на отпускание мыши, не "отскакивает" в начало
  • Транспорт: Start/End/Mid, Prev/Next marker, ±1s, Loop A/B, Space — Play/Pause
  • Monitor processed: прослушка обработанного файла до сохранения; включается автоматически после рендера
  • Автосегментация: режим Silence + фолбэк — если не нашли разрывы, режем хотя бы через Min(s)
  • Обновление playhead'а только когда плеер реально играет (без дерганья в покое)
- Process: крутилки выровнены, превью Tone/Match‑EQ сохранено
"""
from __future__ import annotations
import os
import sys
import csv
from typing import List, Tuple, Optional

import numpy as np
import soundfile as sf

APP_VERSION = 'UnifyAudio r9.4.4'

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QMediaDevices

from Core import (
    ProcParams,
    process_signal,
    read_audio_any,
    to_sr_mono,
    avg_mag_spectrum,
    compute_match_filter,
    crossfade_concat,
    estimate_snr,
    TARGET_SR,
)
from widgets import apply_dark_theme, make_tile
from controls import Knob, EqPreview
from workers import SegWorker


# ---------- Shared state ----------
class SharedState(QtCore.QObject):
    segmentsChanged = QtCore.Signal(list)      # list[(a,b,name,role,is_ref)]
    audioLoaded = QtCore.Signal(str, int)      # file_path, sr
    processedReady = QtCore.Signal(str, list)  # out_path, rows

    def __init__(self):
        super().__init__()
        self.params = ProcParams()
        self.file_path: Optional[str] = None
        self.ref_path: Optional[str] = None
        self.out_dir: Optional[str] = None
        self.last_x: Optional[np.ndarray] = None
        self.sr: int = TARGET_SR
        self.segments_meta: List[Tuple[int, int, str, str, bool]] = []
        self.rows: list = []
        self.processed_path: Optional[str] = None


# ---------- Waveform/segment editor ----------
class SegmentEditor(QtWidgets.QGraphicsView):
    segmentsChanged = QtCore.Signal(list)
    cursorChanged = QtCore.Signal(float)
    playRequested = QtCore.Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setBackgroundBrush(QtGui.QColor("#0f1115"))
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)

        self.samples = 0
        self.sr = TARGET_SR
        self.min_seg_s = 3.0
        self.margin = 30

        self.segment_lines: list[QtWidgets.QGraphicsLineItem] = []
        self.segment_rects: list[QtWidgets.QGraphicsRectItem] = []
        self.segments_meta: list[Tuple[int, int, str, str, bool]] = []

        self.wave_item = None
        self.playhead_item = None
        self._duration_s = 0.0
        self._zoom_x = 1.0

        self._env_len = 0
        self._cursor_sec = 0.0

    # ---- audio / drawing ----
    def set_audio(self, x: np.ndarray, sr: int):
        self.scene.clear()
        self.segment_lines.clear()
        self.segment_rects.clear()
        self.segments_meta.clear()

        self.samples = len(x)
        self.sr = sr
        self._duration_s = self.samples / float(self.sr) if self.sr else 0.0

        H = 320
        target_points = min(3600, max(900, self.samples // 140))
        step = max(1, self.samples // target_points)
        max_env = []
        min_env = []
        for i in range(0, self.samples, step):
            chunk = x[i : i + step]
            if len(chunk) == 0:
                mx = 0.0
                mn = 0.0
            else:
                mx = float(np.max(chunk))
                mn = float(np.min(chunk))
            max_env.append(mx)
            min_env.append(mn)
        max_env = np.asarray(max_env, dtype=np.float32)
        min_env = np.asarray(min_env, dtype=np.float32)
        self._env_len = len(max_env)

        W = max(1000, self._env_len)
        self.scene.setSceneRect(0, 0, W + 2 * self.margin, H + 2 * self.margin)
        mid_y = self.margin + H / 2

        poly = QtGui.QPolygonF()
        for i, v in enumerate(max_env):
            y = mid_y - (v * (H * 0.95))
            poly.append(QtCore.QPointF(self.margin + i, y))
        for i in reversed(range(len(min_env))):
            v = min_env[i]
            y = mid_y - (v * (H * 0.95))
            poly.append(QtCore.QPointF(self.margin + i, y))

        brush = QtGui.QBrush(QtGui.QColor("#66bb6a"))
        pen = QtGui.QPen(QtGui.QColor("#8bd28e"))
        pen.setWidthF(0.6)
        self.wave_item = self.scene.addPolygon(poly, pen, brush)
        self.wave_item.setOpacity(0.70)

        self.scene.addLine(self.margin, mid_y, self.margin + len(max_env), mid_y, QtGui.QPen(QtGui.QColor("#2a2e33")))

        self.playhead_item = self.scene.addLine(self.margin, self.margin, self.margin, self.margin + H, QtGui.QPen(QtGui.QColor("#77c36f"), 2))
        self._draw_time_ruler(W, H)

        QtCore.QTimer.singleShot(0, self.fit_width)

    def _draw_time_ruler(self, W, H):
        pen = QtGui.QPen(QtGui.QColor("#42464b"))
        y = self.margin + H
        for i in range(0, W, 100):
            self.scene.addLine(self.margin + i, y, self.margin + i, y + 6, pen)
        txt = self.scene.addText("Time")
        txt.setDefaultTextColor(QtGui.QColor("#9aa0a6"))
        txt.setPos(self.margin, y + 8)

    # ---- playhead/cursor ----
    def set_playhead_seconds(self, t: float):
        if self._duration_s <= 0:
            return
        t = max(0.0, min(t, self._duration_s))
        usable = max(1.0, self.scene.width() - 2 * self.margin)
        x = self.margin + (t / self._duration_s) * usable
        if self.playhead_item:
            self.playhead_item.setLine(x, self.margin, x, self.scene.height() - self.margin)

    def set_cursor_seconds(self, t: float):
        t = max(0.0, min(t, self._duration_s))
        self._cursor_sec = t
        self.cursorChanged.emit(t)
        self.set_playhead_seconds(t)

    def _x_to_seconds(self, x: float) -> float:
        usable = max(1.0, (self.scene.width() - 2 * self.margin))
        rel = (x - self.margin) / usable
        rel = min(max(rel, 0.0), 1.0)
        return rel * self._duration_s if self._duration_s > 0 else 0.0

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        super().mousePressEvent(e)
        sx = self.mapToScene(e.pos()).x()
        self.set_cursor_seconds(self._x_to_seconds(sx))

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        # при зажатой ЛКМ обновляем cursor по текущей позиции
        if e.buttons() & QtCore.Qt.LeftButton:
            sx = self.mapToScene(e.pos()).x()
            self.set_cursor_seconds(self._x_to_seconds(sx))
        super().mouseMoveEvent(e)

    def mouseDoubleClickEvent(self, e: QtGui.QMouseEvent):
        pos = self.mapToScene(e.pos())
        sx = pos.x()
        nearest = None
        dmin = 99999
        for ln in self.segment_lines:
            d = abs(ln.line().x1() - sx)
            if d < dmin:
                dmin, nearest = d, ln
        if nearest and dmin < 6:
            self.scene.removeItem(nearest)
            self.segment_lines.remove(nearest)
        else:
            self._add_marker_at_x(sx)
        self.set_cursor_seconds(self._x_to_seconds(sx))
        self.emit_segments()

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() == QtCore.Qt.Key_Space:
            self.playRequested.emit(self._cursor_sec); e.accept(); return
        super().keyPressEvent(e)

    def _add_marker_at_x(self, x_scene: float):
        line = self.scene.addLine(x_scene, self.margin - 5, x_scene, self.scene.height() - self.margin + 5, QtGui.QPen(QtGui.QColor("#4caf50"), 2))
        line.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        line.setCursor(QtCore.Qt.SplitHCursor)
        self.segment_lines.append(line)

    def add_marker_at_cursor(self):
        x = self.playhead_item.line().x1() if self.playhead_item else (self.margin + 50)
        self._add_marker_at_x(x)
        self.emit_segments()

    def clear_markers(self):
        for ln in list(self.segment_lines):
            self.scene.removeItem(ln)
        self.segment_lines.clear()
        self.emit_segments()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        super().mouseReleaseEvent(e)
        # фикс: на отпускание — курсор остаётся там, где отпустили
        sx = self.mapToScene(e.pos()).x()
        self.set_cursor_seconds(self._x_to_seconds(sx))
        self.emit_segments()

    def emit_segments(self):
        points = [0] + sorted([self.x_to_sample(m.line().x1()) for m in self.segment_lines]) + [self.samples]
        min_len = int(self.min_seg_s * self.sr)
        out = []
        for i in range(len(points) - 1):
            a, b = points[i], points[i + 1]
            if b - a >= min_len:
                out.append((a, b, f"Seg {i+1}", "", False))
        self.segments_meta = out
        self.segmentsChanged.emit(out)

    def sample_to_x(self, s: int) -> float:
        if self.samples == 0:
            return self.margin
        usable = max(1.0, (self.scene.width() - 2 * self.margin))
        return self.margin + usable * (s / self.samples)

    def x_to_sample(self, x: float) -> int:
        usable = max(1.0, (self.scene.width() - 2 * self.margin))
        rel = (x - self.margin) / usable
        rel = min(max(rel, 0.0), 1.0)
        return int(rel * self.samples)

    # ---- zoom/pan (horizontal only) ----
    def fit_width(self):
        if self.scene is None:
            return
        scene_w = max(1.0, self.scene.sceneRect().width())
        view_w = max(1.0, self.viewport().width())
        sx = max(0.05, (view_w - 2 * 6) / scene_w)
        self._zoom_x = sx
        self._apply_zoom()

    def zoom_reset(self):
        self._zoom_x = 1.0
        self._apply_zoom()

    def zoom_in(self):
        self._zoom_x = min(20.0, self._zoom_x * 1.25)
        self._apply_zoom()

    def zoom_out(self):
        self._zoom_x = max(0.05, self._zoom_x / 1.25)
        self._apply_zoom()

    def _apply_zoom(self):
        t = QtGui.QTransform()
        t.scale(self._zoom_x, 1.0)
        self.setTransform(t)

    def wheelEvent(self, e: QtGui.QWheelEvent):
        if e.modifiers() & QtCore.Qt.ControlModifier:
            delta = e.angleDelta().y()
            self.zoom_in() if delta > 0 else self.zoom_out()
        else:
            dx = -e.angleDelta().y()
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() + dx)
        e.accept()


# ---------- Player (single) ----------
class PlayerWidget(QtWidgets.QWidget):
    positionChanged = QtCore.Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine_combo = QtWidgets.QComboBox(self); self.engine_combo.addItems(["Qt", "ASIO/PortAudio"])
        self.device_combo = QtWidgets.QComboBox(self)
        self.reload_btn = QtWidgets.QToolButton(self); self.reload_btn.setText("⟳"); self.reload_btn.setFixedWidth(26)
        self.btn_play = QtWidgets.QToolButton(self); self.btn_play.setText("▶"); self.btn_play.setFixedWidth(26)
        self.btn_stop = QtWidgets.QToolButton(self); self.btn_stop.setText("■"); self.btn_stop.setFixedWidth(26)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self); self.slider.setRange(0, 1000)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)
        lay.addWidget(QtWidgets.QLabel("Engine:", self))
        lay.addWidget(self.engine_combo)
        lay.addWidget(QtWidgets.QLabel("Device:", self))
        lay.addWidget(self.device_combo, 1)
        lay.addWidget(self.reload_btn)
        lay.addWidget(self.btn_play)
        lay.addWidget(self.btn_stop)
        lay.addWidget(self.slider)

        self.player = QMediaPlayer(self)
        self.audio_out = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_out)
        self.player.positionChanged.connect(self._on_qt_pos)
        self.player.durationChanged.connect(self._on_qt_dur)
        self.player.playbackStateChanged.connect(self._on_qt_state)
        self._qt_duration = 0

        self._sd_available = False
        try:
            import sounddevice as sd  # type: ignore
            self._sd = sd
            self._sd_available = True
        except Exception:
            self._sd = None

        self._sd_sr = TARGET_SR
        self._sd_data = None

        self.reload_btn.clicked.connect(self.reload_devices)
        self.engine_combo.currentIndexChanged.connect(self.reload_devices)
        self.device_combo.currentIndexChanged.connect(self.set_output_device)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.stop)
        self.slider.sliderReleased.connect(self._on_slider_seek)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self.reload_devices()

        # loop state + play state
        self.loop_enabled = False
        self.loop_a = 0.0
        self.loop_b = 0.0
        self._is_playing = False
        self._last_path: Optional[str] = None

    def is_playing(self) -> bool:
        return bool(self._is_playing)

    def _on_qt_state(self, st):
        self._is_playing = (st == QMediaPlayer.PlaybackState.PlayingState)

    def set_loop(self, a: float, b: float):
        self.loop_a = max(0.0, min(a, b))
        self.loop_b = max(self.loop_a, b)
        self.loop_enabled = True

    def clear_loop(self):
        self.loop_enabled = False

    def reload_devices(self):
        self.device_combo.clear()
        if self.engine_combo.currentText() == "ASIO/PortAudio" and self._sd_available:
            try:
                devs = self._sd.query_devices()
                outs = [(i, d) for i, d in enumerate(devs) if d.get("max_output_channels", 0) > 0]
                for i, d in outs:
                    try:
                        hostapi = self._sd.query_hostapis(d.get("hostapi", 0))["name"]
                    except Exception:
                        hostapi = ""
                    self.device_combo.addItem(f"{i}: {d.get('name','?')} ({hostapi})", i)
            except Exception:
                self.device_combo.addItem("Default", None)
        else:
            for dev in QMediaDevices.audioOutputs():
                self.device_combo.addItem(dev.description(), dev)

    def set_output_device(self):
        if self.engine_combo.currentText() == "Qt":
            dev = self.device_combo.currentData()
            try:
                if dev is not None:
                    self.audio_out.setDevice(dev)
            except Exception:
                pass

    def load(self, path: str):
        self._last_path = path
        if self.engine_combo.currentText() == "ASIO/PortAudio" and self._sd_available:
            try:
                data, sr = sf.read(path, dtype="float32")
                if isinstance(data, np.ndarray) and data.ndim == 2:
                    data = data.mean(axis=1)
                self._sd_sr = int(sr)
                self._sd_data = data
            except Exception:
                self._sd_data = None
        else:
            self.player.setSource(QtCore.QUrl.fromLocalFile(path))
            self.set_output_device()

    def seek_to(self, t: float):
        if self.engine_combo.currentText() == "ASIO/PortAudio":
            self.play_from(t)
        else:
            self.player.setPosition(int(max(0.0, t) * 1000))

    def play_from(self, start_s: float):
        if self.engine_combo.currentText() == "ASIO/PortAudio" and self._sd_available and self._sd_data is not None:
            try:
                self._sd.stop()
            except Exception:
                pass
            if self.loop_enabled and self.loop_b > self.loop_a:
                a = int(self.loop_a * self._sd_sr)
                b = int(self.loop_b * self._sd_sr)
                self._sd.play(self._sd_data[a:b], self._sd_sr, device=self.device_combo.currentData())
            else:
                self._sd.play(self._sd_data[int(start_s * self._sd_sr):], self._sd_sr, device=self.device_combo.currentData())
            self._is_playing = True
        else:
            if self.loop_enabled and self.loop_b > self.loop_a:
                self.player.setPosition(int(self.loop_a * 1000))
                self.player.play()
            else:
                self.player.setPosition(int(max(0.0, start_s) * 1000))
                self.player.play()
            # _is_playing обновится из _on_qt_state

    def toggle_play(self):
        if (self.engine_combo.currentText() == "ASIO/PortAudio" and self._sd_available and self._sd_data is not None):
            try:
                if self._is_playing:
                    self._sd.stop()
                    self._is_playing = False
                else:
                    self.play_from(0.0)
            except Exception:
                self.play_from(0.0)
        else:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()  # _is_playing обновится из _on_qt_state
            else:
                self.player.play()

    def stop(self):
        if self._sd_available:
            try:
                self._sd.stop()
            except Exception:
                pass
        self._is_playing = False
        self.player.stop()

    def _on_qt_pos(self, pos_ms: int):
        t = pos_ms / 1000.0
        if self.loop_enabled and self.loop_b > self.loop_a:
            if t >= self.loop_b - 0.01:
                self.player.setPosition(int(self.loop_a * 1000))
                return
        self.positionChanged.emit(t)
        if self._qt_duration > 0:
            self.slider.blockSignals(True)
            self.slider.setValue(int(1000.0 * pos_ms / max(1, self._qt_duration)))
            self.slider.blockSignals(False)

    def _on_qt_dur(self, dur_ms: int):
        self._qt_duration = dur_ms

    def _on_slider_seek(self):
        if self._qt_duration > 0 and self.engine_combo.currentText() == "Qt":
            frac = self.slider.value() / 1000.0
            self.player.setPosition(int(self._qt_duration * frac))

    def _tick(self):
        if self.engine_combo.currentText() == "Qt" and self._qt_duration > 0:
            pos = self.player.position()
            self.slider.blockSignals(True)
            self.slider.setValue(int(1000.0 * pos / max(1, self._qt_duration)))
            self.slider.blockSignals(False)
            self.positionChanged.emit(pos / 1000.0)

    def play_segment(self, start_s: float = 0.0, end_s: Optional[float] = None):
        if (self.engine_combo.currentText() == "ASIO/PortAudio" and self._sd_available and self._sd_data is not None):
            dev_index = self.device_combo.currentData()
            a = int(max(0.0, start_s) * self._sd_sr)
            b = int(end_s * self._sd_sr) if end_s else len(self._sd_data)
            a = max(0, min(a, len(self._sd_data)))
            b = max(a, min(b, len(self._sd_data)))
            try:
                self._sd.stop()
            except Exception:
                pass
            self._sd.play(self._sd_data[a:b], self._sd_sr, device=dev_index)
            self._is_playing = True
        else:
            self.player.setPosition(int(max(0.0, start_s) * 1000))
            self.player.play()


# ---------- Edit Tab ----------
class EditTab(QtWidgets.QWidget):
    def __init__(self, shared: SharedState, parent=None):
        super().__init__(parent)
        self.shared = shared
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Header compact row
        self.file_edit = QtWidgets.QLineEdit(self); self.file_edit.setPlaceholderText("Input audio…")
        self.btn_browse = QtWidgets.QToolButton(self); self.btn_browse.setText("…"); self.btn_browse.setFixedWidth(28)
        self.ref_edit = QtWidgets.QLineEdit(self); self.ref_edit.setPlaceholderText("Reference (optional)…")
        self.btn_ref = QtWidgets.QToolButton(self); self.btn_ref.setText("🎚"); self.btn_ref.setFixedWidth(28)
        self.out_edit = QtWidgets.QLineEdit(self); self.out_edit.setPlaceholderText("Output dir…")
        self.btn_out = QtWidgets.QToolButton(self); self.btn_out.setText("📁"); self.btn_out.setFixedWidth(28)
        self.preset_combo = QtWidgets.QComboBox(self)
        self.preset_combo.addItems(["Podcast","Audiobook","YouTube","Clean Lecture","Broadcast EBU-R128","Film Dialog Stem"])
        self.btn_apply_preset = QtWidgets.QToolButton(self); self.btn_apply_preset.setText("✓"); self.btn_apply_preset.setFixedWidth(28)

        head = QtWidgets.QGridLayout()
        head.setHorizontalSpacing(6); head.setVerticalSpacing(2)
        head.addWidget(QtWidgets.QLabel("In:", self), 0, 0)
        head.addWidget(self.file_edit, 0, 1)
        head.addWidget(self.btn_browse, 0, 2)
        head.addWidget(QtWidgets.QLabel("Ref:", self), 0, 3)
        head.addWidget(self.ref_edit, 0, 4)
        head.addWidget(self.btn_ref, 0, 5)
        head.addWidget(QtWidgets.QLabel("Out:", self), 0, 6)
        head.addWidget(self.out_edit, 0, 7)
        head.addWidget(self.btn_out, 0, 8)
        head.addWidget(self.preset_combo, 0, 9)
        head.addWidget(self.btn_apply_preset, 0, 10)
        head.setColumnStretch(1, 3); head.setColumnStretch(4, 2); head.setColumnStretch(7, 3); head.setColumnStretch(9, 1)

        # Playback (devices + basic controls)
        self.player = PlayerWidget(self)

        # Waveform
        self.editor = SegmentEditor(self)
        self.editor.setMinimumHeight(320)
        self.editor.setMaximumHeight(320)
        self.editor.playRequested.connect(self._on_play_requested)

        # Transport panel
        self.btn_start = QtWidgets.QToolButton(self); self.btn_start.setText("|<<")
        self.btn_prev = QtWidgets.QToolButton(self); self.btn_prev.setText("<<")
        self.btn_play = QtWidgets.QToolButton(self); self.btn_play.setText("▶/▮▮")
        self.btn_stop = QtWidgets.QToolButton(self); self.btn_stop.setText("■")
        self.btn_next = QtWidgets.QToolButton(self); self.btn_next.setText(">>")
        self.btn_end = QtWidgets.QToolButton(self); self.btn_end.setText(">>|")
        self.btn_mid = QtWidgets.QToolButton(self); self.btn_mid.setText("Mid")
        self.btn_prev_m = QtWidgets.QToolButton(self); self.btn_prev_m.setText("[ Prev")
        self.btn_next_m = QtWidgets.QToolButton(self); self.btn_next_m.setText("Next ]")
        self.btn_loop = QtWidgets.QToolButton(self); self.btn_loop.setText("Loop ⟳"); self.btn_loop.setCheckable(True)
        self.btn_setA = QtWidgets.QToolButton(self); self.btn_setA.setText("Set A")
        self.btn_setB = QtWidgets.QToolButton(self); self.btn_setB.setText("Set B")
        self.cb_monitor_proc = QtWidgets.QCheckBox("Monitor processed", self); self.cb_monitor_proc.setChecked(False)

        tp = QtWidgets.QHBoxLayout()
        tp.setContentsMargins(0,0,0,0); tp.setSpacing(6)
        for w in [self.btn_start, self.btn_prev, self.btn_play, self.btn_stop, self.btn_next, self.btn_end, self.btn_mid, self.btn_prev_m, self.btn_next_m, self.btn_loop, self.btn_setA, self.btn_setB, self.cb_monitor_proc]:
            tp.addWidget(w)
        tp.addStretch(1)

        # Zoom bar
        self.btn_fit = QtWidgets.QToolButton(self); self.btn_fit.setText("Fit")
        self.btn_100 = QtWidgets.QToolButton(self); self.btn_100.setText("100%")
        self.btn_zm_out = QtWidgets.QToolButton(self); self.btn_zm_out.setText("−")
        self.btn_zm_in = QtWidgets.QToolButton(self); self.btn_zm_in.setText("+")
        zb = QtWidgets.QHBoxLayout()
        zb.setContentsMargins(0,0,0,0); zb.setSpacing(6)
        zb.addWidget(QtWidgets.QLabel("Zoom:", self))
        zb.addWidget(self.btn_zm_out); zb.addWidget(self.btn_zm_in)
        zb.addWidget(self.btn_fit); zb.addWidget(self.btn_100)
        zb.addStretch(1)

        # Marker tools (with autosplit controls)
        self.btn_add_marker = QtWidgets.QToolButton(self); self.btn_add_marker.setText("Add at cursor")
        self.btn_clear_markers = QtWidgets.QToolButton(self); self.btn_clear_markers.setText("Clear")
        self.sb_min = QtWidgets.QDoubleSpinBox(self); self.sb_min.setRange(2.0, 30.0); self.sb_min.setValue(6.0); self.sb_min.setSingleStep(0.5)
        self.mode_combo = QtWidgets.QComboBox(self); self.mode_combo.addItems(["Silence","Voice change","Energy","Embeddings (opt)","BIC"])
        self.sb_sens = QtWidgets.QDoubleSpinBox(self); self.sb_sens.setRange(0.1, 3.0); self.sb_sens.setValue(1.0); self.sb_sens.setSingleStep(0.1)
        self.btn_run_seg = QtWidgets.QPushButton("Auto", self)
        self.lab_seg_status = QtWidgets.QLabel("", self)
        mt = QtWidgets.QHBoxLayout()
        mt.setContentsMargins(0,0,0,0); mt.setSpacing(6)
        mt.addWidget(QtWidgets.QLabel("Markers:", self))
        mt.addWidget(self.btn_add_marker)
        mt.addWidget(self.btn_clear_markers)
        mt.addWidget(QtWidgets.QLabel("Min (s):", self)); mt.addWidget(self.sb_min)
        mt.addWidget(QtWidgets.QLabel("Mode:", self)); mt.addWidget(self.mode_combo)
        mt.addWidget(QtWidgets.QLabel("Sens:", self)); mt.addWidget(self.sb_sens)
        mt.addWidget(self.btn_run_seg)
        mt.addWidget(self.lab_seg_status)
        mt.addStretch(1)

        # Table
        self.table = QtWidgets.QTableWidget(0, 8, self)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Character", "Ref?", "Start", "End", "Dur", "Processed file"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(20)

        # Hotkeys
        self._sc_space = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Space), self); self._sc_space.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        self._sc_space.activated.connect(self._on_space_shortcut)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Home), self, activated=lambda: self.go_to("start"))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_End), self, activated=lambda: self.go_to("end"))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_M), self, activated=lambda: self.go_to("mid"))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_L), self, activated=self.toggle_loop)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_BracketLeft), self, activated=self.prev_marker)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_BracketRight), self, activated=self.next_marker)

        # Layout
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(6)
        root.addLayout(head)
        root.addWidget(QtWidgets.QLabel("Playback device:", self))
        root.addWidget(self.player)
        root.addWidget(QtWidgets.QLabel("Waveform:", self))
        root.addLayout(tp)
        root.addLayout(zb)
        root.addWidget(self.editor)
        root.addLayout(mt)
        root.addWidget(QtWidgets.QLabel("Segments:", self))
        root.addWidget(self.table)

        # Signals
        self.btn_browse.clicked.connect(self.browse_file)
        self.btn_ref.clicked.connect(self.browse_ref)
        self.btn_out.clicked.connect(self.browse_out)
        self.btn_apply_preset.clicked.connect(self.apply_preset)
        self.btn_run_seg.clicked.connect(self.run_auto_segmentation)
        self.table.cellChanged.connect(self.on_table_edit)
        self.editor.segmentsChanged.connect(self.on_segments_from_editor)

        # ВАЖНО: обновляем playhead от плеера только когда он играет
        self.player.positionChanged.connect(self.on_player_pos)

        # transport
        self.btn_play.clicked.connect(self._on_space_shortcut)
        self.btn_stop.clicked.connect(self.player.stop)
        self.btn_start.clicked.connect(lambda: self.go_to("start"))
        self.btn_end.clicked.connect(lambda: self.go_to("end"))
        self.btn_prev.clicked.connect(lambda: self.nudge(-1.0))
        self.btn_next.clicked.connect(lambda: self.nudge(1.0))
        self.btn_mid.clicked.connect(lambda: self.go_to("mid"))
        self.btn_prev_m.clicked.connect(self.prev_marker)
        self.btn_next_m.clicked.connect(self.next_marker)
        self.btn_loop.toggled.connect(self.on_loop_toggled)
        self.btn_setA.clicked.connect(self.set_loop_a)
        self.btn_setB.clicked.connect(self.set_loop_b)
        # zoom
        self.btn_fit.clicked.connect(self.editor.fit_width)
        self.btn_100.clicked.connect(self.editor.zoom_reset)
        self.btn_zm_in.clicked.connect(self.editor.zoom_in)
        self.btn_zm_out.clicked.connect(self.editor.zoom_out)
        # markers
        self.btn_add_marker.clicked.connect(self.editor.add_marker_at_cursor)
        self.btn_clear_markers.clicked.connect(self.editor.clear_markers)

        # loop points
        self._loop_a = 0.0
        self._loop_b = 0.0

        # threads
        self.thread_seg: Optional[QtCore.QThread] = None
        self.worker_seg: Optional[SegWorker] = None

    # ---- Player position follow (only while playing) ----
    @QtCore.Slot(float)
    def on_player_pos(self, t: float):
        if self.player.is_playing():
            self.editor.set_playhead_seconds(t)

    # ---- Transport helpers ----
    def on_loop_toggled(self, on: bool):
        if on and self._loop_b > self._loop_a:
            self.player.set_loop(self._loop_a, self._loop_b)
        else:
            self.player.clear_loop()

    def set_loop_a(self):
        line = self.editor.playhead_item.line() if self.editor.playhead_item else None
        t = self.editor._x_to_seconds(line.x1()) if line else 0.0
        self._loop_a = t
        self.on_loop_toggled(self.btn_loop.isChecked())

    def set_loop_b(self):
        line = self.editor.playhead_item.line() if self.editor.playhead_item else None
        t = self.editor._x_to_seconds(line.x1()) if line else 0.0
        self._loop_b = max(t, self._loop_a + 0.01)
        self.on_loop_toggled(self.btn_loop.isChecked())

    def toggle_loop(self):
        self.btn_loop.toggle()

    def nudge(self, dt: float):
        line = self.editor.playhead_item.line() if self.editor.playhead_item else None
        cur = self.editor._x_to_seconds(line.x1()) if line else 0.0
        self.set_cursor(cur + dt)

    def prev_marker(self):
        cur = self.current_time()
        xs = sorted([self.editor._x_to_seconds(ln.line().x1()) for ln in self.editor.segment_lines])
        xs = [t for t in xs if t < cur - 1e-3]
        if xs:
            self.set_cursor(xs[-1])

    def next_marker(self):
        cur = self.current_time()
        xs = sorted([self.editor._x_to_seconds(ln.line().x1()) for ln in self.editor.segment_lines])
        xs = [t for t in xs if t > cur + 1e-3]
        if xs:
            self.set_cursor(xs[0])

    def go_to(self, where: str):
        if where == "start":
            t = 0.0
        elif where == "end":
            t = (self.editor._duration_s if self.editor._duration_s else 0.0)
        else:  # mid
            t = (self.editor._duration_s or 0.0) / 2.0
        self.set_cursor(t)

    def current_time(self) -> float:
        line = self.editor.playhead_item.line() if self.editor.playhead_item else None
        return self.editor._x_to_seconds(line.x1()) if line else 0.0

    def _current_play_path(self) -> Optional[str]:
        # если есть обработанный и выбран монитор — играем его
        if self.cb_monitor_proc.isChecked() and self.shared.processed_path and os.path.isfile(self.shared.processed_path):
            return self.shared.processed_path
        # иначе — оригинал
        return self.shared.file_path if (self.shared.file_path and os.path.isfile(self.shared.file_path)) else None

    def set_cursor(self, t: float):
        self.editor.set_cursor_seconds(t)
        path = self._current_play_path()
        if path:
            if self.player._last_path != path:
                self.player.load(path)
            self.player.seek_to(t)

    # ---- Space to play from cursor ----
    def _on_space_shortcut(self):
        path = self._current_play_path()
        if path:
            if self.player._last_path != path:
                self.player.load(path)
            t = self.current_time()
            if self.player.engine_combo.currentText() == "Qt" and self.player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.toggle_play()
            else:
                self.player.play_from(t)

    # ---- called by editor.playRequested (по клику/пробелу на волне) ----
    def _on_play_requested(self, t: float):
        self.editor.set_cursor_seconds(t)
        path = self._current_play_path()
        if path:
            if self.player._last_path != path:
                self.player.load(path)
            self.player.play_from(t)

    # ---- Presets ----
    def apply_preset(self):
        name = self.preset_combo.currentText()
        presets = {
            "Podcast": ProcParams(post_lufs=-16.0, pre_lufs=-23.0, denoise=True, denoise_reduction_db=12,
                                  dereverb_enable=False, dereverb_amount=0.4, eq_max_gain_db=6, eq_match_weight=0.9,
                                  tilt_db_per_oct=-0.4, bass_guard_hz=140.0, bass_guard_max_boost_db=1.5,
                                  comp_thresh_db=-26, comp_ratio=2.8, comp_attack_ms=12, comp_release_ms=80,
                                  deess_amount_db=7, limiter_ceiling_db=-1.0, limiter_truepeak=True,
                                  sat_drive_db=2.0, sat_mix=0.15, exciter_amount=0.05, exciter_fc=4500.0),
            "Audiobook": ProcParams(post_lufs=-18.0, pre_lufs=-23.0, denoise=True, denoise_reduction_db=8,
                                    dereverb_enable=False, dereverb_amount=0.3, eq_max_gain_db=4, eq_match_weight=0.8,
                                    tilt_db_per_oct=-0.2, bass_guard_hz=150.0, bass_guard_max_boost_db=1.0,
                                    comp_thresh_db=-28, comp_ratio=2.2, comp_attack_ms=20, comp_release_ms=120,
                                    deess_amount_db=4, limiter_ceiling_db=-1.0, limiter_truepeak=True),
            "YouTube": ProcParams(post_lufs=-14.0, pre_lufs=-22.0, denoise=True, denoise_reduction_db=10,
                                  dereverb_enable=True, dereverb_amount=0.5, eq_max_gain_db=6, eq_match_weight=1.0,
                                  tilt_db_per_oct=-0.6, bass_guard_hz=140.0, bass_guard_max_boost_db=1.5,
                                  comp_thresh_db=-24, comp_ratio=3.0, comp_attack_ms=10, comp_release_ms=80,
                                  deess_amount_db=6, limiter_ceiling_db=-1.0, limiter_truepeak=True,
                                  sat_drive_db=3.0, sat_mix=0.2, exciter_amount=0.1, exciter_fc=4500.0),
            "Clean Lecture": ProcParams(post_lufs=-19.0, pre_lufs=-23.5, denoise=True, denoise_reduction_db=10,
                                        dereverb_enable=True, dereverb_amount=0.55, eq_max_gain_db=5, eq_match_weight=0.9,
                                        tilt_db_per_oct=-0.3, bass_guard_hz=160.0, bass_guard_max_boost_db=1.2,
                                        comp_thresh_db=-25, comp_ratio=2.0, comp_attack_ms=18, comp_release_ms=110,
                                        deess_amount_db=3, limiter_ceiling_db=-1.0, limiter_truepeak=True),
            "Broadcast EBU-R128": ProcParams(post_lufs=-23.0, pre_lufs=-27.0, denoise=True, denoise_reduction_db=8,
                                             dereverb_enable=False, dereverb_amount=0.3, eq_max_gain_db=4, eq_match_weight=0.7,
                                             tilt_db_per_oct=-0.2, bass_guard_hz=150.0, bass_guard_max_boost_db=1.0,
                                             comp_thresh_db=-27, comp_ratio=2.0, comp_attack_ms=25, comp_release_ms=150,
                                             deess_amount_db=3, limiter_ceiling_db=-1.0, limiter_truepeak=True),
            "Film Dialog Stem": ProcParams(post_lufs=-24.0, pre_lufs=-27.0, denoise=True, denoise_reduction_db=6,
                                           dereverb_enable=True, dereverb_amount=0.4, eq_max_gain_db=4, eq_match_weight=0.8,
                                           tilt_db_per_oct=-0.2, bass_guard_hz=160.0, bass_guard_max_boost_db=1.0,
                                           comp_thresh_db=-30, comp_ratio=1.8, comp_attack_ms=25, comp_release_ms=160,
                                           deess_amount_db=3, limiter_ceiling_db=-2.0, limiter_truepeak=True,
                                           sat_drive_db=1.0, sat_mix=0.1, exciter_amount=0.0, exciter_fc=5000.0),
        }
        self.shared.params = presets[name]
        QtWidgets.QMessageBox.information(self, "Preset", f"Applied preset: {name}")

    # ---- Paths ----
    def browse_file(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select audio", "", "Audio (*.wav *.flac *.ogg *.mp3 *.m4a)")
        if p:
            self.file_edit.setText(p)
            self.shared.file_path = p
            self.load_audio(p)

    def browse_ref(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select reference", "", "Audio (*.wav *.flac *.ogg *.mp3 *.m4a)")
        if p:
            self.ref_edit.setText(p)
            self.shared.ref_path = p

    def browse_out(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Output directory")
        if d:
            self.out_edit.setText(d)
            self.shared.out_dir = d

    # ---- Analyze / Segmentation ----
    def load_audio(self, fp: str):
        x, sr = read_audio_any(fp)
        x, sr = to_sr_mono(x, sr, TARGET_SR)
        self.shared.last_x = x
        self.shared.sr = sr
        self.editor.set_audio(x, sr)
        # По умолчанию мониторим оригинал
        self.cb_monitor_proc.setChecked(False)
        self.player.load(fp)
        self.shared.audioLoaded.emit(fp, sr)

    def run_auto_segmentation(self):
        if self.shared.last_x is None or self.shared.sr <= 0:
            QtWidgets.QMessageBox.warning(self, "No audio", "Load input audio first")
            return
        x = self.shared.last_x
        sr = self.shared.sr
        min_s = float(self.sb_min.value())
        sens = float(self.sb_sens.value())
        idx = self.mode_combo.currentIndex()
        mode = {0: "silence", 1: "voice", 2: "energy", 3: "emb", 4: "bic"}[idx]

        self.lab_seg_status.setText("Analyzing…")
        self.worker_seg = SegWorker(x.copy(), sr, min_seg_s=min_s, sensitivity=sens, mode=mode)
        self.thread_seg = QtCore.QThread(self)
        self.worker_seg.moveToThread(self.thread_seg)
        self.thread_seg.started.connect(self.worker_seg.run)
        self.worker_seg.done.connect(self.on_seg_done)
        self.worker_seg.error.connect(self.on_seg_error)
        self.thread_seg.start()

    @QtCore.Slot(list)
    def on_seg_done(self, segs):
        try:
            self.thread_seg.quit(); self.thread_seg.wait()
        except Exception:
            pass
        if not segs and self.shared.last_x is not None:
            segs = [(0, len(self.shared.last_x))]
        self.editor.set_segments(segs)
        self.fill_table_from_editor()
        self.lab_seg_status.setText(f"Found {len(segs)} segments")

    @QtCore.Slot(str)
    def on_seg_error(self, msg):
        try:
            self.thread_seg.quit(); self.thread_seg.wait()
        except Exception:
            pass
        self.lab_seg_status.setText("Error")
        QtWidgets.QMessageBox.critical(self, "Segmentation error", msg)

    def on_segments_from_editor(self, segs_meta_simple):
        self.editor.min_seg_s = float(self.sb_min.value())
        self.fill_table_from_editor(segs_meta_simple)

    def fill_table_from_editor(self, segs_meta_simple=None):
        if segs_meta_simple is None:
            segs_meta_simple = self.editor.segments_meta
        self.table.blockSignals(True)
        self.table.setRowCount(len(segs_meta_simple))
        for i, (a, b, name, role, is_ref) in enumerate(segs_meta_simple):
            dur = (b - a) / self.editor.sr if self.editor.sr else 0.0
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(name))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(role))
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            chk.setCheckState(QtCore.Qt.Checked if is_ref else QtCore.Qt.Unchecked)
            self.table.setItem(i, 3, chk)
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"{a/self.editor.sr:.2f}"))
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(f"{b/self.editor.sr:.2f}"))
            self.table.setItem(i, 6, QtWidgets.QTableWidgetItem(f"{dur:.2f}"))
            self.table.setItem(i, 7, QtWidgets.QTableWidgetItem(""))
        self.table.blockSignals(False)
        self.shared.segments_meta = self.collect_segments_meta()
        self.shared.segmentsChanged.emit(self.shared.segments_meta)

    def collect_segments_meta(self):
        segs = []
        for i in range(self.table.rowCount()):
            a = float(self.table.item(i, 4).text())
            b = float(self.table.item(i, 5).text())
            name = self.table.item(i, 1).text() if self.table.item(i, 1) else f"Seg {i+1}"
            role = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            is_ref = self.table.item(i, 3).checkState() == QtCore.Qt.Checked
            sa = int(a * TARGET_SR)
            sb = int(b * TARGET_SR)
            segs.append((sa, sb, name, role, is_ref))
        return segs

    def on_table_edit(self, row, col):
        if col == 3:
            for i in range(self.table.rowCount()):
                if i != row:
                    it = self.table.item(i, 3)
                    if it:
                        it.setCheckState(QtCore.Qt.Unchecked)
        self.shared.segments_meta = self.collect_segments_meta()
        self.shared.segmentsChanged.emit(self.shared.segments_meta)

    # автоподхват обработанного файла — включаем монитор processed
    @QtCore.Slot(str, list)
    def on_processed_ready(self, out_path: str, rows: list):
        self.shared.processed_path = out_path
        self.cb_monitor_proc.setChecked(True)
        # если сейчас открыт другой путь — перелoad на обработанный
        if self.player._last_path != out_path:
            self.player.load(out_path)


# ---------- Process Tab (knobs aligned + preview) ----------
class ProcessTab(QtWidgets.QWidget):
    def __init__(self, shared: 'SharedState', parent=None):
        super().__init__(parent)
        self.shared = shared

        # --- Tone/Match‑EQ with preview ---
        tone_box = QtWidgets.QWidget(self)
        gl = QtWidgets.QGridLayout(tone_box)
        gl.setContentsMargins(8, 8, 8, 8)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(8)

        self.eq_preview = EqPreview(self)
        self.kn_match = Knob("Match", 0, 100, 1, "%", 100)
        self.kn_tilt = Knob("Tilt", -3.0, 3.0, 0.1, " dB/oct", 0.0)
        self.kn_bg_hz = Knob("BassHz", 60, 240, 1, " Hz", 140)
        self.kn_bg_max = Knob("MaxBoost", 0.0, 6.0, 0.1, " dB", 1.5)
        for kb in [self.kn_match, self.kn_tilt, self.kn_bg_hz, self.kn_bg_max]:
            kb.setFixedWidth(120)

        self.cb_render_bypass = QtWidgets.QCheckBox("Bypass render", self)
        self.cb_render_bypass.setChecked(False)
        self.btn_process = QtWidgets.QPushButton("Process", self)

        self.hint = QtWidgets.QTextBrowser(self); self.hint.setFixedHeight(80)
        self.hint.setStyleSheet("QTextBrowser{background:#15191e;border:1px solid #2d333b;color:#bfc6cd;}")

        gl.addWidget(self.eq_preview, 0, 0, 1, 6)
        gl.addWidget(self.kn_match, 1, 0)
        gl.addWidget(self.kn_tilt, 1, 1)
        gl.addWidget(self.kn_bg_hz, 1, 2)
        gl.addWidget(self.kn_bg_max, 1, 3)
        ctl_row = QtWidgets.QHBoxLayout(); ctl_row.addWidget(self.cb_render_bypass); ctl_row.addStretch(1); ctl_row.addWidget(self.btn_process)
        gl.addLayout(ctl_row, 1, 4, 1, 2)
        gl.addWidget(self.hint, 2, 0, 1, 6)

        w_tone = make_tile("Tone / Match‑EQ", tone_box, collapsible=False)

        # --- Clean (knobs) ---
        clean = QtWidgets.QWidget(self)
        lc = QtWidgets.QGridLayout(clean); lc.setContentsMargins(8, 8, 8, 8); lc.setHorizontalSpacing(10); lc.setVerticalSpacing(8)
        self.cb_dn = QtWidgets.QCheckBox("Denoise", clean); self.cb_dn.setChecked(True)
        self.kn_dn = Knob("Reduction", 0.0, 24.0, 0.5, " dB", 12.0)
        self.cb_drv = QtWidgets.QCheckBox("Dereverb", clean); self.cb_drv.setChecked(False)
        self.kn_drv = Knob("Amount", 0.0, 100.0, 1.0, " %", 50.0)
        self.kn_deess = Knob("De‑esser", 0.0, 12.0, 0.5, " dB", 6.0)
        for kb in [self.kn_dn, self.kn_drv, self.kn_deess]:
            kb.setFixedWidth(120)
        lc.addWidget(self.cb_dn, 0, 0); lc.addWidget(self.kn_dn, 0, 1)
        lc.addWidget(self.cb_drv, 0, 2); lc.addWidget(self.kn_drv, 0, 3)
        lc.addWidget(self.kn_deess, 0, 4)
        w_clean = make_tile("Clean", clean, collapsible=False)

        # --- Dynamics (knobs) ---
        dyn = QtWidgets.QWidget(self)
        ld = QtWidgets.QGridLayout(dyn); ld.setContentsMargins(8, 8, 8, 8); ld.setHorizontalSpacing(10); ld.setVerticalSpacing(8)
        self.cb_gate = QtWidgets.QCheckBox("Gate", dyn)
        self.kn_gate_open = Knob("Gate Open", -80.0, -10.0, 1.0, " dB", -45.0)
        self.kn_gate_close = Knob("Gate Close", -90.0, -12.0, 1.0, " dB", -50.0)
        self.kn_gate_ratio = Knob("Gate Ratio", 1.0, 4.0, 0.1, ":1", 1.5)
        self.kn_ct = Knob("Comp Thresh", -50.0, -6.0, 1.0, " dB", -24.0)
        self.kn_cr = Knob("Comp Ratio", 1.0, 6.0, 0.1, ":1", 2.5)
        self.kn_ca = Knob("Attack", 1.0, 40.0, 1.0, " ms", 15.0)
        self.kn_crl = Knob("Release", 20.0, 250.0, 5.0, " ms", 90.0)
        for kb in [self.kn_gate_open, self.kn_gate_close, self.kn_gate_ratio, self.kn_ct, self.kn_cr, self.kn_ca, self.kn_crl]:
            kb.setFixedWidth(120)
        ld.addWidget(self.cb_gate, 0, 0)
        ld.addWidget(self.kn_gate_open, 0, 1)
        ld.addWidget(self.kn_gate_close, 0, 2)
        ld.addWidget(self.kn_gate_ratio, 0, 3)
        ld.addWidget(self.kn_ct, 1, 0)
        ld.addWidget(self.kn_cr, 1, 1)
        ld.addWidget(self.kn_ca, 1, 2)
        ld.addWidget(self.kn_crl, 1, 3)
        w_dyn = make_tile("Dynamics", dyn, collapsible=False)

        # --- Color (knobs) ---
        col = QtWidgets.QWidget(self)
        lc2 = QtWidgets.QGridLayout(col); lc2.setContentsMargins(8, 8, 8, 8); lc2.setHorizontalSpacing(10); lc2.setVerticalSpacing(8)
        self.kn_sat = Knob("Saturation", 0.0, 6.0, 0.5, " dB", 0.0)
        self.kn_satmix = Knob("Sat Mix", 0.0, 1.0, 0.05, "", 0.2)
        self.kn_exc = Knob("Exciter", 0.0, 0.5, 0.05, "", 0.0)
        self.kn_excf = Knob("Exciter Fc", 2000.0, 10000.0, 100.0, " Hz", 4000.0)
        for kb in [self.kn_sat, self.kn_satmix, self.kn_exc, self.kn_excf]:
            kb.setFixedWidth(120)
        lc2.addWidget(self.kn_sat, 0, 0)
        lc2.addWidget(self.kn_satmix, 0, 1)
        lc2.addWidget(self.kn_exc, 0, 2)
        lc2.addWidget(self.kn_excf, 0, 3)
        w_col = make_tile("Color", col, collapsible=False)

        # --- Output (knobs) ---
        outw = QtWidgets.QWidget(self)
        lo = QtWidgets.QGridLayout(outw); lo.setContentsMargins(8, 8, 8, 8); lo.setHorizontalSpacing(10); lo.setVerticalSpacing(8)
        self.kn_pre = Knob("Pre-LUFS", -35.0, -10.0, 0.5, " LUFS", -23.0)
        self.kn_post = Knob("Post-LUFS", -30.0, -10.0, 0.5, " LUFS", -19.0)
        self.kn_lim = Knob("Ceiling", -6.0, -0.1, 0.1, " dBFS", -1.0)
        for kb in [self.kn_pre, self.kn_post, self.kn_lim]:
            kb.setFixedWidth(120)
        self.cb_tp = QtWidgets.QCheckBox("TruePeak", outw); self.cb_tp.setChecked(True)
        lo.addWidget(self.kn_pre, 0, 0)
        lo.addWidget(self.kn_post, 0, 1)
        lo.addWidget(self.kn_lim, 0, 2)
        lo.addWidget(self.cb_tp, 0, 3)
        w_out = make_tile("Output", outw, collapsible=False)

        # Export/status
        self.btn_export = QtWidgets.QPushButton("Export…", self)
        self.btn_export_csv = QtWidgets.QPushButton("Export CSV/EDL…", self)
        self.progress = QtWidgets.QProgressBar(self)
        self.status = QtWidgets.QLabel("Ready", self)

        actions = QtWidgets.QHBoxLayout(); actions.setContentsMargins(0,0,0,0); actions.setSpacing(6)
        actions.addWidget(self.btn_export); actions.addWidget(self.btn_export_csv); actions.addStretch(1)

        # Root
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(8)
        root.addWidget(w_tone)
        grid = QtWidgets.QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
        grid.addWidget(w_clean, 0, 0)
        grid.addWidget(w_dyn, 0, 1)
        grid.addWidget(w_col, 1, 0)
        grid.addWidget(w_out, 1, 1)
        root.addLayout(grid)
        root.addLayout(actions)
        root.addWidget(self.progress)
        root.addWidget(self.status)

        # Signals
        self.btn_process.clicked.connect(self.process)
        self.btn_export.clicked.connect(self.export_file)
        self.btn_export_csv.clicked.connect(self.export_csv)

        # Hints + preview
        self.kn_match.setHint("Насколько сильно подгонять спектр сегмента под референс (0–100%).")
        self.kn_tilt.setHint("Наклон тона: − теплее/темнее, + ярче/светлее.")
        self.kn_bg_hz.setHint("Частота защиты баса — ниже неё Match ограничивает усиление.")
        self.kn_bg_max.setHint("Максимальный подъём в зоне баса.")
        for kb in [self.kn_match, self.kn_tilt, self.kn_bg_hz, self.kn_bg_max]:
            kb.valueChanged.connect(self._update_tone_preview)
        self._update_tone_preview()

    def _update_tone_preview(self, *_):
        self.eq_preview.setParams(
            tilt_db_oct=self.kn_tilt.value(),
            bass_fc=self.kn_bg_hz.value(),
            bass_max=self.kn_bg_max.value(),
            weight=self.kn_match.value() / 100.0,
        )

    # ---- params sync ----
    def _ui_to_params(self):
        p = self.shared.params
        p.eq_match_weight = self.kn_match.value() / 100.0
        p.tilt_db_per_oct = float(self.kn_tilt.value())
        p.bass_guard_hz = float(self.kn_bg_hz.value())
        p.bass_guard_max_boost_db = float(self.kn_bg_max.value())
        p.denoise = self.cb_dn.isChecked()
        p.denoise_reduction_db = float(self.kn_dn.value())
        p.dereverb_enable = self.cb_drv.isChecked()
        p.dereverb_amount = float(self.kn_drv.value()) / 100.0
        p.deess_amount_db = float(self.kn_deess.value())
        p.gate_enable = self.cb_gate.isChecked()
        p.gate_open_db = float(self.kn_gate_open.value())
        p.gate_close_db = float(self.kn_gate_close.value())
        p.gate_ratio = float(self.kn_gate_ratio.value())
        p.comp_thresh_db = float(self.kn_ct.value())
        p.comp_ratio = float(self.kn_cr.value())
        p.comp_attack_ms = float(self.kn_ca.value())
        p.comp_release_ms = float(self.kn_crl.value())
        p.sat_drive_db = float(self.kn_sat.value())
        p.sat_mix = float(self.kn_satmix.value())
        p.exciter_amount = float(self.kn_exc.value())
        p.exciter_fc = float(self.kn_excf.value())
        p.pre_lufs = float(self.kn_pre.value())
        p.post_lufs = float(self.kn_post.value())
        p.limiter_ceiling_db = float(self.kn_lim.value())
        p.limiter_truepeak = self.cb_tp.isChecked()

    # ---- processing / export ----
    def process(self):
        if not self.shared.file_path or not os.path.isfile(self.shared.file_path):
            QtWidgets.QMessageBox.warning(self, "Oops", "Select input file on Edit tab"); return
        if not self.shared.out_dir:
            QtWidgets.QMessageBox.warning(self, "Oops", "Select output directory on Edit tab"); return
        if not self.shared.segments_meta:
            QtWidgets.QMessageBox.warning(self, "Oops", "Set segments/markers on Edit tab"); return

        self._ui_to_params()
        bypass_render = self.cb_render_bypass.isChecked()
        self.progress.setValue(0)
        self.status.setText("Processing…")

        worker = _InlineMagicWorker(self.shared.file_path, self.shared.out_dir, self.shared.params,
                                    segments_meta=self.shared.segments_meta, ref_file=self.shared.ref_path,
                                    bypass_render=bypass_render)
        th = QtCore.QThread(self); self._proc_thread = th; self._proc_worker = worker
        worker.moveToThread(th)
        th.started.connect(worker.run)
        worker.progress.connect(self.progress.setValue)
        worker.status.connect(self.status.setText)
        worker.error.connect(self.on_error)
        worker.done.connect(self.on_done)
        th.start()

    def export_file(self):
        if not self.shared.processed_path or not os.path.isfile(self.shared.processed_path):
            QtWidgets.QMessageBox.information(self, "No data", "Process the file first"); return
        p, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save output", "unified.wav", "WAV (*.wav)")
        if p:
            data, sr = sf.read(self.shared.processed_path, dtype="float32"); sf.write(p, data, sr, subtype="PCM_24")
            QtWidgets.QMessageBox.information(self, "OK", f"Saved: {p}")

    def export_csv(self):
        if not self.shared.rows:
            QtWidgets.QMessageBox.information(self, "No data", "Process the file first"); return
        p, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV/EDL", "segments.csv", "CSV (*.csv)")
        if p:
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["#", "Name", "Character", "Start", "End", "Duration", "ProcessedFile"])
                for r, (idx, name, role, orig, proc, a, b) in enumerate(self.shared.rows):
                    w.writerow([idx + 1, name, role, f"{a:.3f}", f"{b:.3f}", f"{b-a:.3f}", proc])
            QtWidgets.QMessageBox.information(self, "OK", f"Saved: {p}")

    @QtCore.Slot(str)
    def on_error(self, msg):
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        try:
            if hasattr(self, "_proc_thread") and self._proc_thread:
                self._proc_thread.quit(); self._proc_thread.wait()
        except Exception:
            pass

    @QtCore.Slot(str, list, np.ndarray, int)
    def on_done(self, out_path: str, rows: list, y_all: np.ndarray, sr: int):
        try:
            if hasattr(self, "_proc_thread") and self._proc_thread:
                self._proc_thread.quit(); self._proc_thread.wait()
        except Exception:
            pass
        self.status.setText(f"Done: {out_path}")
        self.shared.processed_path = out_path
        self.shared.rows = rows
        self.shared.processedReady.emit(out_path, rows)
        self.progress.setValue(100)


# ---------- Inline worker ----------
class _InlineMagicWorker(QtCore.QObject):
    progress = QtCore.Signal(int)
    status = QtCore.Signal(str)
    done = QtCore.Signal(str, list, np.ndarray, int)
    error = QtCore.Signal(str)

    def __init__(self, file_path: str, out_dir: str, params: ProcParams,
                 segments_meta: Optional[List[Tuple[int, int, str, str, bool]]] = None,
                 ref_file: Optional[str] = None, bypass_render: bool = False):
        super().__init__()
        self.file_path = file_path
        self.out_dir = out_dir
        self.params = params
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="unify_magic_")
        self.segments_meta = segments_meta
        self.ref_file = ref_file
        self.bypass_render = bool(bypass_render)

    @QtCore.Slot()
    def run(self):
        try:
            self.status.emit("Reading file…")
            x, sr = read_audio_any(self.file_path)
            x, sr = to_sr_mono(x, sr, TARGET_SR)

            segs = self.segments_meta or [(0, len(x), "Seg 1", "", False)]
            self.status.emit(f"Segments: {len(segs)}")

            if self.ref_file and os.path.isfile(self.ref_file):
                r, rr = read_audio_any(self.ref_file); r, rr = to_sr_mono(r, rr, TARGET_SR)
                ref_avg = avg_mag_spectrum(r, rr)
            else:
                ref_idx = next((i for i, (_, _, _, _, is_ref) in enumerate(segs) if is_ref), None)
                if ref_idx is None:
                    ref_idx = int(np.argmax([estimate_snr(x[a:b], sr) for (a, b, *_rest) in segs]))
                a_ref, b_ref, *_ = segs[ref_idx]; ref_avg = avg_mag_spectrum(x[a_ref:b_ref], sr)

            n_fft = 4096
            proc_chunks = []; rows = []
            for i, (a, b, name, role, is_ref) in enumerate(segs):
                self.progress.emit(int(100 * (i / max(1, len(segs)))))
                self.status.emit(f"Processing segment {i+1}/{len(segs)}…")
                if self.bypass_render:
                    y = x[a:b].astype(np.float32)
                else:
                    cur_avg = avg_mag_spectrum(x[a:b], sr)
                    H = compute_match_filter(ref_avg, cur_avg, sr, n_fft,
                                             max_gain_db=self.params.eq_max_gain_db,
                                             weight=self.params.eq_match_weight,
                                             bass_guard_hz=self.params.bass_guard_hz,
                                             bass_guard_max_boost_db=self.params.bass_guard_max_boost_db,
                                             tilt_db_per_oct=self.params.tilt_db_per_oct)
                    y = process_signal(x[a:b], sr, H, self.params)
                proc_chunks.append(y)
                import os as _os
                orig_path = _os.path.join(self.tmpdir, f"seg_{i:03d}_orig.wav")
                proc_path = _os.path.join(self.tmpdir, f"seg_{i:03d}_proc.wav")
                sf.write(orig_path, x[a:b], sr); sf.write(proc_path, y, sr)
                rows.append((i, name, role, orig_path, proc_path, a / sr, b / sr))

            self.status.emit("Stitching…")
            y_all = crossfade_concat(proc_chunks, sr, xf_ms=10.0)
            os.makedirs(self.out_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(self.file_path))[0]
            out_path = os.path.join(self.out_dir, f"{base}_unified.wav")
            sf.write(out_path, y_all, sr, subtype="PCM_24")
            self.progress.emit(100); self.status.emit("Done.")
            self.done.emit(out_path, rows, y_all, sr)
        except Exception as e:
            self.error.emit(str(e))


# ---------- Main window ----------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unify Audio")
        self.resize(1260, 710)

        self.shared = SharedState()
        tabs = QtWidgets.QTabWidget(self)
        self.edit_tab = EditTab(self.shared, self)
        self.proc_tab = ProcessTab(self.shared, self)
        tabs.addTab(self.edit_tab, "Edit")
        tabs.addTab(self.proc_tab, "Process")
        self.setCentralWidget(tabs)

        # когда обработка готова — включить монитор processed на вкладке Edit
        self.shared.processedReady.connect(self.edit_tab.on_processed_ready)

    @QtCore.Slot(str, list)
    def _on_processed_ready(self, out_path: str, rows: list):
        pass


def main():
    app = QtWidgets.QApplication(sys.argv)
    try:
        apply_dark_theme(app, base_font_point_size=9)
    except Exception:
        pass
    win = MainWindow()
    win.setWindowTitle(f"Unify Audio – {APP_VERSION}")
    print("AudioUnify:", APP_VERSION, "from", os.path.abspath(__file__))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()