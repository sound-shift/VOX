from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from app.audio.media_io import read_audio_mono
from app.dsp.pipeline import ProcessingOptions, process_take


def test_read_audio_mono_wav(tmp_path):
    path = tmp_path / "tone.wav"
    sr = 48000
    samples = [0, 10000, -10000, 5000] * 1000
    with wave.open(path.as_posix(), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    data, out_sr = read_audio_mono(path, sr)
    assert out_sr == sr
    assert len(data) == len(samples)


def test_pipeline_bypass():
    signal = [0.1] * 48000
    result = process_take(signal, 48000, ProcessingOptions(bypass=True))
    assert len(result.processed) == len(signal)


def test_pipeline_with_isolation():
    import math

    sr = 48000
    signal = [0.1 * math.sin(2 * math.pi * 440 * i / sr) for i in range(sr)]
    opts = ProcessingOptions(preset_key="male_low", isolation_amount=0.3, match_weight=0.0)
    result = process_take(signal, sr, opts)
    assert len(result.processed) == len(signal)
    assert abs(result.report.integrated_lufs - (-23.0)) < 4.0
