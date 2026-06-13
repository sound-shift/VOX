"""Load audio from WAV, FLAC, MP3 and other formats."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

from app.audio.engine import TARGET_SR, read_wav_mono, write_wav_mono
from third_party.ffmpeg.finder import find_ffmpeg

AUDIO_IMPORT_FILTER = "Audio (*.wav *.flac *.mp3 *.ogg *.m4a *.aac *.wma);;All files (*.*)"


def read_audio_mono(path: Path, target_sr: int = TARGET_SR) -> tuple[List[float], int]:
    """Decode any supported audio file to mono float samples."""
    path = path.resolve()
    suffix = path.suffix.lower()

    if suffix == ".wav":
        return read_wav_mono(path, target_sr)

    try:
        return _read_with_soundfile(path, target_sr)
    except Exception:
        return _read_with_ffmpeg(path, target_sr)


def _read_with_soundfile(path: Path, target_sr: int) -> tuple[List[float], int]:
    import numpy as np
    import soundfile as sf
    from app.legacy.unify.core import to_sr_mono

    data, sr = sf.read(path.as_posix(), always_2d=False)
    if data.ndim == 2:
        data = (data[:, 0] + data[:, 1]) * 0.5
    mono = data.astype("float32", copy=False)
    mono, sr = to_sr_mono(mono, int(sr), target_sr)
    return mono.tolist(), sr


def _read_with_ffmpeg(path: Path, target_sr: int) -> tuple[List[float], int]:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError(
            f"Cannot decode {path.suffix}: install FFmpeg or use WAV. "
            "Place ffmpeg in third_party/ffmpeg/ or PATH."
        )
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        ffmpeg.as_posix(),
        "-y",
        "-i",
        path.as_posix(),
        "-ac",
        "1",
        "-ar",
        str(target_sr),
        tmp_path.as_posix(),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return read_wav_mono(tmp_path, target_sr)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.decode("utf-8", errors="ignore")[:500]) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def extract_audio_from_video(video_path: Path, target: Path, target_sr: int = TARGET_SR) -> tuple[List[float], int]:
    """Extract mono audio track from a video file via FFmpeg."""
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("FFmpeg required for video import.")
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg.as_posix(),
        "-y",
        "-i",
        video_path.resolve().as_posix(),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(target_sr),
        target.as_posix(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return read_wav_mono(target, target_sr)


__all__ = ["read_audio_mono", "extract_audio_from_video", "AUDIO_IMPORT_FILTER"]
