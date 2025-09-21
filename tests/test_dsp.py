from __future__ import annotations

import math

from app.dsp.magic import process_magic


def test_magic_processing_loudness_targets():
    sr = 48000
    duration = 1.0
    signal = [0.1 * math.sin(2 * math.pi * 220.0 * (i / sr)) for i in range(int(sr * duration))]
    result = process_magic(signal, sr, "male_low")
    assert abs(result.report.integrated_lufs - (-23.0)) < 3.0
    assert result.report.true_peak <= -1.0 + 1.0
