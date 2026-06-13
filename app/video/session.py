"""Video session for ADR — preview + synced audio bed."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.audio.media_io import extract_audio_from_video


@dataclass
class VideoSession:
    video_path: Optional[Path] = None
    extracted_audio_path: Optional[Path] = None
    duration_sec: float = 0.0

    def load(self, video_path: Path, project_dir: Path, sample_rate: int = 48000) -> tuple[list[float], int]:
        self.video_path = video_path.resolve()
        audio_dir = project_dir / "video"
        audio_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_audio_path = audio_dir / "picture_lock.wav"
        data, sr = extract_audio_from_video(self.video_path, self.extracted_audio_path, sample_rate)
        self.duration_sec = len(data) / sr if data else 0.0
        return data, sr

    def clear(self) -> None:
        self.video_path = None
        self.extracted_audio_path = None
        self.duration_sec = 0.0


__all__ = ["VideoSession"]
