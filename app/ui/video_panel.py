"""Video preview panel for ADR."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui import palette


class VideoPanel(QtWidgets.QFrame):
    """Picture lock preview synced with transport."""

    importRequested = QtCore.Signal()
    seekRequested = QtCore.Signal(float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoPanel")
        self.setStyleSheet(
            f"""
            QFrame#videoPanel {{
                background: {palette.BG_DEEP};
                border-bottom: 1px solid {palette.BORDER};
            }}
            """
        )
        self._path: Optional[Path] = None
        self._adr_mode = False
        self._player = None
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("PICTURE LOCK")
        title.setObjectName("sectionTitle")
        self.lbl_time = QtWidgets.QLabel("00:00.0")
        self.lbl_time.setStyleSheet(
            f"color: {palette.ACCENT_ORANGE}; font-family: Consolas, monospace; font-size: 12px;"
        )
        self.lbl_file = QtWidgets.QLabel("No video loaded")
        self.lbl_file.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 11px;")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(self.lbl_time)
        header.addStretch(1)
        header.addWidget(self.lbl_file)
        self.btn_import = QtWidgets.QPushButton("Import Video…")
        self.btn_import.setObjectName("primaryBtn")
        self.btn_import.clicked.connect(self.importRequested.emit)
        header.addWidget(self.btn_import)
        layout.addLayout(header)

        self._stack = QtWidgets.QStackedWidget(self)

        self._placeholder = QtWidgets.QFrame()
        ph_layout = QtWidgets.QVBoxLayout(self._placeholder)
        ph_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        ph_icon = QtWidgets.QLabel("🎬")
        ph_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        ph_icon.setStyleSheet("font-size: 36px;")
        ph_text = QtWidgets.QLabel(
            "Load a video to dub in sync.\n"
            "Use File → Import Video or the button above.\n"
            "Playback follows the transport bar below."
        )
        ph_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        ph_text.setWordWrap(True)
        ph_text.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-size: 12px;")
        ph_layout.addWidget(ph_icon)
        ph_layout.addWidget(ph_text)

        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget

            self._video_page = QtWidgets.QWidget()
            video_layout = QtWidgets.QVBoxLayout(self._video_page)
            video_layout.setContentsMargins(0, 0, 0, 0)
            self._video_widget = QVideoWidget(self._video_page)
            self._video_widget.setMinimumHeight(220)
            self._video_widget.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            self._video_widget.setStyleSheet(f"background: #000; border-radius: 6px;")
            self._video_widget.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self._video_widget.installEventFilter(self)
            video_layout.addWidget(self._video_widget)
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video_widget)
            self._stack.addWidget(self._placeholder)
            self._stack.addWidget(self._video_page)
        except Exception:
            fallback = QtWidgets.QLabel(
                "Install PySide6-QtMultimediaWidgets for video preview.\n"
                "Audio ADR still works via the Picture Lock track.",
                self,
            )
            fallback.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._stack.addWidget(fallback)

        layout.addWidget(self._stack, stretch=1)
        self.setMinimumHeight(260)

    def set_adr_mode(self, enabled: bool) -> None:
        self._adr_mode = enabled
        if enabled and self._path is None:
            self.setVisible(True)
            self._stack.setCurrentWidget(self._placeholder)
        elif not enabled and self._path is None:
            self.setVisible(False)

    def load(self, path: Path) -> None:
        self._path = path.resolve()
        self.lbl_file.setText(self._path.name)
        self.setVisible(True)
        if self._player is not None:
            from PySide6.QtCore import QUrl

            self._player.setSource(QUrl.fromLocalFile(str(self._path)))
            self._stack.setCurrentWidget(self._video_page)
        self._video_widget.show()

    def clear(self) -> None:
        self._path = None
        self.lbl_file.setText("No video loaded")
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QtCore.QUrl())
            self._stack.setCurrentWidget(self._placeholder)
        if not self._adr_mode:
            self.setVisible(False)

    def seek(self, seconds: float) -> None:
        if self._player is not None:
            self._player.setPosition(int(max(0.0, seconds) * 1000))
        mins = int(seconds // 60)
        secs = seconds % 60
        self.lbl_time.setText(f"{mins:02d}:{secs:04.1f}")

    def play(self) -> None:
        if self._player is not None:
            self._player.play()

    def pause(self) -> None:
        if self._player is not None:
            self._player.pause()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()

    def set_muted(self, muted: bool) -> None:
        if self._player is not None and hasattr(self, "_audio"):
            self._audio.setMuted(muted)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is getattr(self, "_video_widget", None) and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if self._player is not None and self._path is not None:
                duration_ms = self._player.duration()
                if duration_ms > 0:
                    frac = event.position().x() / max(1.0, self._video_widget.width())
                    sec = max(0.0, min(duration_ms / 1000.0, frac * duration_ms / 1000.0))
                    self.seekRequested.emit(sec)
                    return True
        return super().eventFilter(obj, event)

    @property
    def path(self) -> Optional[Path]:
        return self._path


__all__ = ["VideoPanel"]
