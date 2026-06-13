"""Video preview panel for ADR."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.ui import palette


class VideoPanel(QtWidgets.QFrame):
    """Picture lock preview synced with transport."""

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
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("PICTURE LOCK")
        title.setObjectName("sectionTitle")
        self.lbl_file = QtWidgets.QLabel("No video")
        self.lbl_file.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 11px;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lbl_file)
        layout.addLayout(header)

        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QUrl
            from PySide6.QtMultimediaWidgets import QVideoWidget

            self._video_widget = QVideoWidget(self)
            self._video_widget.setMinimumHeight(180)
            self._video_widget.setMaximumHeight(280)
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video_widget)
            self._has_video = True
        except Exception:
            self._video_widget = QtWidgets.QLabel("Video preview requires QtMultimediaWidgets", self)
            self._player = None
            self._has_video = False

        layout.addWidget(self._video_widget)

    def load(self, path: Path) -> None:
        self._path = path.resolve()
        self.lbl_file.setText(self._path.name)
        self.setVisible(True)
        if self._player is not None:
            from PySide6.QtCore import QUrl

            self._player.setSource(QUrl.fromLocalFile(str(self._path)))
        self._video_widget.show()

    def clear(self) -> None:
        self._path = None
        self.lbl_file.setText("No video")
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QtCore.QUrl())
        self.setVisible(False)

    def seek(self, seconds: float) -> None:
        if self._player is not None:
            self._player.setPosition(int(max(0.0, seconds) * 1000))

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

    @property
    def path(self) -> Optional[Path]:
        return self._path


__all__ = ["VideoPanel"]
