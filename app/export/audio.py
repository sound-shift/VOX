"""Audio export helpers derived from Unify's exporter."""
from __future__ import annotations

import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.dsp import loudness
from third_party.ffmpeg.finder import find_ffmpeg


class ExportError(RuntimeError):
    pass


@dataclass
class ExportResult:
    path: Path
    format: str
    report: loudness.LoudnessReport


class AudioExporter:
    def __init__(self, ffmpeg_dir: Optional[Path] = None) -> None:
        self.ffmpeg_dir = ffmpeg_dir
        self.ffmpeg_path = find_ffmpeg(ffmpeg_dir)

    def export(self, signal: List[float], sr: int, target: Path, fmt: str, mp3_bitrate: int = 192) -> ExportResult:
        target = target.resolve()
        normalized, report = loudness.normalize(signal, sr)
        fmt = fmt.lower()
        if fmt == "wav":
            self._export_wav(normalized, sr, target)
        elif fmt == "flac":
            self._export_flac(normalized, sr, target)
        elif fmt == "mp3":
            self._export_mp3(normalized, sr, target, mp3_bitrate)
        else:
            raise ExportError(f"Unsupported format: {fmt}")
        return ExportResult(path=target, format=fmt, report=report)

    def _export_wav(self, signal: List[float], sr: int, target: Path) -> None:
        with wave.open(target.as_posix(), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(sample * 32767)))) for sample in signal)
            wf.writeframes(frames)

    def _export_flac(self, signal: List[float], sr: int, target: Path) -> None:
        ffmpeg = self.ffmpeg_path
        if ffmpeg is None:
            raise ExportError(
                "FFmpeg binary not found. Place ffmpeg(.exe) in third_party/ffmpeg or add it to PATH."
            )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            self._export_wav(signal, sr, Path(tmp.name))
            tmp.flush()
            cmd = [ffmpeg.as_posix(), "-y", "-i", tmp.name, "-c:a", "flac", target.as_posix()]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as exc:
                raise ExportError(exc.stderr.decode("utf-8", errors="ignore")) from exc

    def _export_mp3(self, signal: List[float], sr: int, target: Path, bitrate: int) -> None:
        ffmpeg = self.ffmpeg_path
        if ffmpeg is None:
            raise ExportError(
                "FFmpeg binary not found. Place ffmpeg(.exe) in third_party/ffmpeg or add it to PATH."
            )
        bitrate = int(bitrate)
        if bitrate not in {128, 160, 192, 256, 320}:
            raise ExportError("MP3 bitrate must be one of 128/160/192/256/320 kbps")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            self._export_wav(signal, sr, Path(tmp.name))
            tmp.flush()
            cmd = [
                ffmpeg.as_posix(),
                "-y",
                "-i",
                tmp.name,
                "-c:a",
                "libmp3lame",
                "-b:a",
                f"{bitrate}k",
                target.as_posix(),
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as exc:
                raise ExportError(exc.stderr.decode("utf-8", errors="ignore")) from exc


__all__ = ["AudioExporter", "ExportResult", "ExportError"]
