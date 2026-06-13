"""Audio transport, recording and preroll helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional

import math
import random
import wave
import struct

from app.timeline.model import Clip, Timeline

BEEP_FREQ = 1000.0
BEEP_DURATION = 0.25
GO_SILENCE = 0.15
TARGET_SR = 48000


@dataclass
class PreRollCue:
    name: str
    data: List[float]


def generate_beep(sr: int, freq: float = BEEP_FREQ, duration: float = BEEP_DURATION) -> List[float]:
    total = int(sr * duration)
    return [0.4 * math.sin(2 * math.pi * freq * (i / sr)) for i in range(total)]


def preroll_sequence(sr: int = TARGET_SR) -> Iterable[PreRollCue]:
    beep = generate_beep(sr)
    silence = [0.0] * int(sr * GO_SILENCE)
    for idx in range(1, 4):
        yield PreRollCue(name=f"beep_{idx}", data=list(beep))
        yield PreRollCue(name=f"pause_{idx}", data=list(silence))
    go_tone = generate_beep(sr, freq=1500.0, duration=0.2)
    yield PreRollCue(name="go", data=go_tone)


@dataclass
class RecordedTake:
    clip: Clip
    data: List[float]
    file_path: Optional[Path]


class Recorder:
    """High level recording helper. The MVP simulates recording via synthetic tones."""

    def __init__(self, timeline: Timeline, sr: int = TARGET_SR) -> None:
        self.timeline = timeline
        self.sample_rate = sr
        self.monitor_processed = False
        self.bypass_processing = False

    def record(self, track_id: int, duration: float, source: Optional[Callable[[int], List[float]]] = None) -> RecordedTake:
        track = self.timeline.get_track(track_id)
        if not track.armed:
            raise RuntimeError("Track must be armed before recording")
        clip = self.timeline.add_clip(track_id, start=0.0, end=duration)
        total_samples = int(self.sample_rate * duration)
        if source is None:
            data = self._simulate_voice(total_samples)
        else:
            data = source(total_samples)
        self.timeline.add_take(clip, data=data, start=0.0, end=duration, active=True)
        file_path = self._write_temp_take(track_id, clip)
        return RecordedTake(clip=clip, data=data, file_path=file_path)

    def _simulate_voice(self, samples: int) -> List[float]:
        out = []
        for i in range(samples):
            t = i / self.sample_rate
            base = 0.1 * math.sin(2 * math.pi * 220.0 * t)
            mod = 0.02 * math.sin(2 * math.pi * 3.0 * t)
            noise = 0.01 * (random.random() * 2.0 - 1.0)
            out.append(base + mod + noise)
        return out

    def _write_temp_take(self, track_id: int, clip: Clip) -> Optional[Path]:
        take = clip.active_take()
        if take is None:
            return None
        tmp_dir = Path(".vox_takes")
        tmp_dir.mkdir(exist_ok=True)
        file_path = tmp_dir / f"track{track_id}_take{take.id}.wav"
        with wave.open(file_path.as_posix(), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(sample * 32767)))) for sample in take.data)
            wf.writeframes(frames)
        return file_path


class Transport:
    def __init__(self, timeline: Timeline, sr: int = TARGET_SR) -> None:
        self.timeline = timeline
        self.sample_rate = sr
        self.playing = False
        self.position = 0.0

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def toggle(self) -> None:
        self.playing = not self.playing

    def locate(self, position: float) -> None:
        self.position = max(0.0, position)


def read_wav_mono(path: Path, target_sr: int = TARGET_SR) -> tuple[List[float], int]:
    with wave.open(path.as_posix(), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if sample_width != 2:
        raise ValueError("Only 16-bit PCM WAV files are supported")
    count = len(frames) // 2
    samples = struct.unpack(f"<{count}h", frames)
    if channels == 2:
        mono = [(samples[i] + samples[i + 1]) / (2 * 32767.0) for i in range(0, len(samples), 2)]
    else:
        mono = [sample / 32767.0 for sample in samples]
    if sr != target_sr and mono:
        ratio = target_sr / sr
        new_len = max(1, int(len(mono) * ratio))
        resampled: List[float] = []
        for i in range(new_len):
            src = i / ratio
            left = int(src)
            right = min(left + 1, len(mono) - 1)
            frac = src - left
            resampled.append(mono[left] * (1.0 - frac) + mono[right] * frac)
        mono = resampled
        sr = target_sr
    return mono, sr


def write_wav_mono(path: Path, data: List[float], sr: int = TARGET_SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(path.as_posix(), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(sample * 32767)))) for sample in data)
        wf.writeframes(frames)


class PlaybackEngine:
    """Play active takes through Qt multimedia."""

    def __init__(self, parent=None) -> None:
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        self._player = QMediaPlayer(parent)
        self._output = QAudioOutput(parent)
        self._player.setAudioOutput(self._output)
        self._temp_path: Optional[Path] = None

    def play_take(self, data: List[float], sr: int = TARGET_SR) -> None:
        from PySide6.QtCore import QUrl

        tmp_dir = Path(".vox_takes")
        tmp_dir.mkdir(exist_ok=True)
        self._temp_path = tmp_dir / "_preview.wav"
        write_wav_mono(self._temp_path, data, sr)
        self._player.setSource(QUrl.fromLocalFile(str(self._temp_path.resolve())))
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def toggle(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def is_playing(self) -> bool:
        from PySide6.QtMultimedia import QMediaPlayer

        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState


__all__ = [
    "Recorder",
    "Transport",
    "PlaybackEngine",
    "preroll_sequence",
    "generate_beep",
    "RecordedTake",
    "read_wav_mono",
    "write_wav_mono",
]
