"""Live microphone capture via Qt Multimedia."""
from __future__ import annotations

import struct
from typing import List

from PySide6 import QtCore

from app.audio.engine import TARGET_SR, preroll_sequence


class _CaptureIODevice(QtCore.QIODevice):
    def __init__(self) -> None:
        super().__init__()
        self._buffer = bytearray()

    def readData(self, maxlen: int) -> bytes:  # noqa: N802
        return b""

    def writeData(self, data: bytes) -> int:  # noqa: N802
        self._buffer.extend(data)
        return len(data)

    def pcm_bytes(self) -> bytes:
        return bytes(self._buffer)


def _bytes_to_float_mono(pcm: bytes) -> List[float]:
    if len(pcm) < 2:
        return []
    count = len(pcm) // 2
    samples = struct.unpack(f"<{count}h", pcm[: count * 2])
    return [sample / 32767.0 for sample in samples]


def microphone_available() -> bool:
    from PySide6.QtMultimedia import QMediaDevices

    return bool(QMediaDevices.audioInputs())


def capture_microphone(duration_sec: float, sr: int = TARGET_SR, with_preroll: bool = True) -> List[float]:
    """Block and capture from default input for *duration_sec* seconds."""
    from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

    device = QMediaDevices.defaultAudioInput()
    if device.isNull():
        raise RuntimeError("No microphone found")

    fmt = QAudioFormat()
    fmt.setSampleRate(sr)
    fmt.setChannelCount(1)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

    buffer = _CaptureIODevice()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    source = QAudioSource(device, fmt)
    source.start(buffer)

    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(int(max(0.1, duration_sec) * 1000), loop.quit)
    loop.exec()
    source.stop()
    buffer.close()

    mic = _bytes_to_float_mono(buffer.pcm_bytes())
    if not with_preroll:
        return mic

    preroll: List[float] = []
    for cue in preroll_sequence(sr):
        preroll.extend(cue.data)
    return preroll + mic


__all__ = ["capture_microphone", "microphone_available"]
