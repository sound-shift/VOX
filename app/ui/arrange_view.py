"""Arrange view — track lanes, waveforms, ruler, playhead."""
from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.timeline.model import Timeline, Track
from app.ui import palette

TRACK_HEADER_W = 148
RULER_H = 34
TRACK_H = 76
MIN_PPSS = 20.0
MAX_PPSS = 400.0
DEFAULT_PPSS = 90.0


def _downsample_waveform(data: List[float], width: int) -> List[float]:
    if not data or width <= 0:
        return []
    if len(data) <= width:
        return [abs(v) for v in data]
    block = max(1, len(data) // width)
    peaks: List[float] = []
    for i in range(width):
        chunk = data[i * block : (i + 1) * block]
        peaks.append(max(abs(x) for x in chunk) if chunk else 0.0)
    return peaks


class ArrangeCanvas(QtWidgets.QWidget):
    trackSelected = QtCore.Signal(int)
    playheadMoved = QtCore.Signal(float)
    armToggled = QtCore.Signal(int)
    takeSelected = QtCore.Signal(int, int)

    def __init__(self, timeline: Timeline, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.timeline = timeline
        self.selected_track_id: Optional[int] = None
        self.playhead_sec = 0.0
        self.pps = DEFAULT_PPSS
        self.loop_in: Optional[float] = None
        self.loop_out: Optional[float] = None
        self.setMouseTracking(True)
        self._recompute_size()

    def refresh(self) -> None:
        if self.selected_track_id is None and self.timeline.tracks:
            self.selected_track_id = next(iter(self.timeline.tracks))
        self._recompute_size()
        self.update()

    def set_playhead(self, seconds: float) -> None:
        self.playhead_sec = max(0.0, seconds)
        self.update()

    def set_zoom(self, delta: float) -> None:
        self.pps = float(max(MIN_PPSS, min(MAX_PPSS, self.pps + delta)))
        self._recompute_size()
        self.update()

    def set_loop_region(self, loop_in: Optional[float], loop_out: Optional[float]) -> None:
        self.loop_in = loop_in
        self.loop_out = loop_out
        self.update()

    def _content_duration(self) -> float:
        end = 30.0
        for track in self.timeline.tracks.values():
            for clip in track.clips:
                end = max(end, clip.end + 2.0)
        return end

    def _recompute_size(self) -> None:
        track_count = max(1, len(self.timeline.tracks))
        width = TRACK_HEADER_W + int(self._content_duration() * self.pps) + 200
        height = RULER_H + track_count * TRACK_H + 12
        self.setMinimumSize(width, height)
        self.resize(width, height)

    def _track_at_y(self, y: float) -> Optional[Track]:
        if y < RULER_H:
            return None
        idx = int((y - RULER_H) // TRACK_H)
        tracks = list(self.timeline.tracks.values())
        if 0 <= idx < len(tracks):
            return tracks[idx]
        return None

    def _sec_at_x(self, x: float) -> float:
        return max(0.0, (x - TRACK_HEADER_W) / self.pps)

    def _clip_hit(self, x: float, y: float) -> tuple[Optional[int], Optional[int]]:
        """Return (clip_id, take_id) if click hits a take lane."""
        track = self._track_at_y(y)
        if track is None or x < TRACK_HEADER_W:
            return None, None
        sec = self._sec_at_x(x)
        tracks = list(self.timeline.tracks.values())
        idx = tracks.index(track)
        y0 = RULER_H + idx * TRACK_H
        rel_y = y - (y0 + 8)
        lane_h = TRACK_H - 16

        for clip in track.clips:
            if not (clip.start <= sec < clip.end):
                continue
            take_count = max(1, len(clip.takes))
            lane_step = lane_h / take_count
            lane_idx = min(take_count - 1, max(0, int(rel_y / max(1.0, lane_step))))
            if 0 <= lane_idx < len(clip.takes):
                return clip.id, clip.takes[lane_idx].id
            return clip.id, None
        return None, None

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        rect = self.rect()
        painter.fillRect(rect, palette.qcolor(palette.BG_DEEP))

        painter.fillRect(0, 0, rect.width(), RULER_H, palette.qcolor(palette.BG_HEADER))
        painter.setPen(palette.qcolor(palette.BORDER))
        painter.drawLine(0, RULER_H, rect.width(), RULER_H)
        painter.drawLine(TRACK_HEADER_W, 0, TRACK_HEADER_W, rect.height())

        duration = self._content_duration()
        end_sec = duration + 2

        sec = 0
        while sec <= int(end_sec):
            x = TRACK_HEADER_W + sec * self.pps
            major = sec % 5 == 0
            painter.setPen(palette.qcolor(palette.GRID_MAJOR if major else palette.GRID_MINOR))
            painter.drawLine(int(x), RULER_H, int(x), rect.height())
            if major:
                painter.setPen(palette.qcolor(palette.TEXT_DIM))
                painter.setFont(QtGui.QFont("Segoe UI", 8))
                painter.drawText(int(x) + 4, 20, f"{sec}s")
            sec += 1

        tracks = list(self.timeline.tracks.values())
        if not tracks:
            painter.setPen(palette.qcolor(palette.TEXT_DIM))
            painter.drawText(TRACK_HEADER_W + 20, RULER_H + 40, "Arm a track (R) and hit Record — or Import WAV")
            painter.end()
            return

        for idx, track in enumerate(tracks):
            y0 = RULER_H + idx * TRACK_H
            selected = track.id == self.selected_track_id
            header_bg = palette.BG_RAISED if selected else palette.BG_TRACK
            painter.fillRect(0, y0, TRACK_HEADER_W, TRACK_H, palette.qcolor(header_bg))
            painter.fillRect(TRACK_HEADER_W, y0, rect.width(), TRACK_H, palette.qcolor(palette.BG_PANEL if idx % 2 == 0 else palette.BG_DEEP))

            arm_rect = QtCore.QRect(10, y0 + 22, 28, 28)
            arm_color = palette.ACCENT_ARM if track.armed else palette.BG_HEADER
            painter.setBrush(palette.qcolor(arm_color))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRoundedRect(arm_rect, 6, 6)
            painter.setPen(palette.qcolor("#000" if track.armed else palette.TEXT_SECONDARY))
            painter.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.Bold))
            painter.drawText(arm_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "R")

            painter.fillRect(44, y0 + 16, 4, TRACK_H - 32, palette.qcolor(track.color))
            painter.setPen(palette.qcolor(palette.TEXT_PRIMARY if selected else palette.TEXT_SECONDARY))
            painter.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.Weight.DemiBold if selected else QtGui.QFont.Weight.Normal))
            painter.drawText(56, y0 + 28, track.name)
            painter.setPen(palette.qcolor(palette.TEXT_DIM))
            painter.setFont(QtGui.QFont("Segoe UI", 8))
            painter.drawText(56, y0 + 46, f"{len(track.clips)} clip(s)")

            for clip in track.clips:
                x_start = TRACK_HEADER_W + clip.start * self.pps
                clip_w = max(8.0, (clip.end - clip.start) * self.pps)
                clip_rect = QtCore.QRectF(x_start, y0 + 8, clip_w, TRACK_H - 16)
                takes = clip.takes if clip.takes else []
                take_count = max(1, len(takes))
                lane_h = clip_rect.height() / take_count

                for lane_idx, take in enumerate(takes if takes else [None]):
                    if take is None or not take.data:
                        continue
                    lane_rect = QtCore.QRectF(
                        clip_rect.x(),
                        clip_rect.y() + lane_idx * lane_h,
                        clip_rect.width(),
                        lane_h - 1,
                    )
                    is_active = take.active
                    wave_color = palette.WAVE_ARMED if track.armed else palette.WAVE_FILL
                    fill = palette.WAVE_FILL_DIM if not is_active else (wave_color if selected else palette.WAVE_FILL_DIM)
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.setBrush(palette.qcolor(fill))
                    painter.setOpacity(0.35 if is_active else 0.15)
                    painter.drawRoundedRect(lane_rect, 3, 3)
                    painter.setOpacity(1.0)

                    if take_count > 1:
                        painter.setPen(palette.qcolor(palette.TEXT_DIM))
                        painter.setFont(QtGui.QFont("Segoe UI", 7, QtGui.QFont.Weight.Bold))
                        label = chr(ord("A") + lane_idx)
                        painter.drawText(int(lane_rect.x()) + 3, int(lane_rect.y()) + 10, label)

                    inner = lane_rect.adjusted(2, 2, -2, -2)
                    peaks = _downsample_waveform(take.data, max(1, int(inner.width())))
                    if peaks:
                        mid = inner.center().y()
                        max_h = max(2.0, inner.height() / 2 - 2)
                        pen_color = wave_color if is_active else palette.WAVE_FILL_DIM
                        painter.setPen(QtGui.QPen(palette.qcolor(pen_color), 1))
                        for i, peak in enumerate(peaks):
                            px = inner.left() + i
                            h = peak * max_h
                            painter.drawLine(int(px), int(mid - h), int(px), int(mid + h))

                if not takes:
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.setBrush(palette.qcolor(palette.WAVE_FILL_DIM))
                    painter.setOpacity(0.12)
                    painter.drawRoundedRect(clip_rect, 4, 4)
                    painter.setOpacity(1.0)

        if self.loop_in is not None and self.loop_out is not None and self.loop_out > self.loop_in:
            lx0 = TRACK_HEADER_W + self.loop_in * self.pps
            lx1 = TRACK_HEADER_W + self.loop_out * self.pps
            painter.fillRect(
                int(lx0),
                RULER_H,
                int(lx1 - lx0),
                rect.height() - RULER_H,
                QtGui.QColor(255, 180, 60, 28),
            )
            painter.setPen(QtGui.QPen(palette.qcolor(palette.ACCENT_ORANGE), 1))
            painter.drawLine(int(lx0), RULER_H, int(lx0), rect.height())
            painter.drawLine(int(lx1), RULER_H, int(lx1), rect.height())

        painter.setPen(QtGui.QPen(palette.qcolor(palette.ACCENT_VIOLET), 1, QtCore.Qt.PenStyle.DashLine))
        for marker in self.timeline.markers.values():
            mx = TRACK_HEADER_W + marker.position * self.pps
            painter.drawLine(int(mx), RULER_H, int(mx), rect.height())
            painter.drawText(int(mx) + 3, RULER_H - 6, marker.name)

        ph_x = TRACK_HEADER_W + self.playhead_sec * self.pps
        painter.setPen(QtGui.QPen(palette.qcolor(palette.ACCENT_ORANGE), 2))
        painter.drawLine(int(ph_x), 0, int(ph_x), rect.height())
        painter.setBrush(palette.qcolor(palette.ACCENT_ORANGE))
        painter.drawPolygon(
            QtGui.QPolygonF(
                [
                    QtCore.QPointF(ph_x - 6, 0),
                    QtCore.QPointF(ph_x + 6, 0),
                    QtCore.QPointF(ph_x, 10),
                ]
            )
        )
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        x, y = event.position().x(), event.position().y()
        if x < TRACK_HEADER_W:
            track = self._track_at_y(y)
            if track is None:
                return
            if 10 <= x <= 38 and y >= RULER_H:
                idx = list(self.timeline.tracks.values()).index(track)
                arm_y0 = RULER_H + idx * TRACK_H
                if arm_y0 + 22 <= y <= arm_y0 + 50:
                    self.armToggled.emit(track.id)
                    return
            self.selected_track_id = track.id
            self.trackSelected.emit(track.id)
            self.update()
            return

        sec = self._sec_at_x(x)
        clip_id, take_id = self._clip_hit(x, y)
        if clip_id is not None and take_id is not None:
            self.takeSelected.emit(clip_id, take_id)
        self.playhead_sec = sec
        self.playheadMoved.emit(sec)
        track = self._track_at_y(y)
        if track is not None:
            self.selected_track_id = track.id
            self.trackSelected.emit(track.id)
        self.update()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = 8.0 if event.angleDelta().y() > 0 else -8.0
            self.set_zoom(delta)
            event.accept()
            return
        super().wheelEvent(event)


class ArrangeView(QtWidgets.QScrollArea):
    """Scrollable wrapper around the arrange canvas."""

    trackSelected = QtCore.Signal(int)
    playheadMoved = QtCore.Signal(float)
    armToggled = QtCore.Signal(int)
    takeSelected = QtCore.Signal(int, int)

    def __init__(self, timeline: Timeline, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.timeline = timeline
        self.selected_track_id: Optional[int] = None
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.canvas = ArrangeCanvas(timeline, self)
        self.setWidget(self.canvas)
        self.canvas.trackSelected.connect(self._on_track_selected)
        self.canvas.playheadMoved.connect(self.playheadMoved.emit)
        self.canvas.armToggled.connect(self.armToggled.emit)
        self.canvas.takeSelected.connect(self.takeSelected.emit)

    def _on_track_selected(self, track_id: int) -> None:
        self.selected_track_id = track_id
        self.trackSelected.emit(track_id)

    def refresh(self) -> None:
        self.canvas.timeline = self.timeline
        self.canvas.refresh()
        if self.selected_track_id is not None:
            self.canvas.selected_track_id = self.selected_track_id

    def set_playhead(self, seconds: float) -> None:
        self.canvas.set_playhead(seconds)

    def set_zoom(self, delta: float) -> None:
        self.canvas.set_zoom(delta)

    def set_loop_region(self, loop_in: Optional[float], loop_out: Optional[float]) -> None:
        self.canvas.set_loop_region(loop_in, loop_out)


__all__ = ["ArrangeView", "DEFAULT_PPSS"]
