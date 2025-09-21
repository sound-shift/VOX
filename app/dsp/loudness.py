"""Simplified loudness measurement and normalization utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import math

TARGET_LUFS = -23.0
TRUE_PEAK_LIMIT = -1.0  # dBTP
OVERSAMPLE = 4


@dataclass
class LoudnessReport:
    integrated_lufs: float
    loudness_range: float
    true_peak: float
    target_lufs: float = TARGET_LUFS

    def as_dict(self) -> dict:
        return {
            "integrated_lufs": self.integrated_lufs,
            "loudness_range": self.loudness_range,
            "true_peak": self.true_peak,
            "target_lufs": self.target_lufs,
        }


def _rms(signal: List[float]) -> float:
    if not signal:
        return 0.0
    return math.sqrt(sum(x * x for x in signal) / len(signal))


def _lufs_from_rms(rms: float) -> float:
    if rms <= 1e-9:
        return -float("inf")
    return -0.691 + 20.0 * math.log10(rms)


def _true_peak(signal: List[float]) -> float:
    if not signal:
        return -120.0
    max_peak = max(abs(s) for s in _oversample(signal, OVERSAMPLE))
    max_peak = max(max_peak, 1e-9)
    return 20.0 * math.log10(max_peak)


def _oversample(signal: List[float], factor: int) -> List[float]:
    if factor <= 1 or len(signal) < 2:
        return list(signal)
    upsampled: List[float] = []
    for i in range(len(signal) - 1):
        a = signal[i]
        b = signal[i + 1]
        upsampled.append(a)
        for k in range(1, factor):
            t = k / factor
            upsampled.append(a + (b - a) * t)
    upsampled.append(signal[-1])
    return upsampled


def measure(signal: List[float], sr: int) -> LoudnessReport:
    rms = _rms(signal)
    integrated = _lufs_from_rms(rms)
    # simplistic loudness range: difference between 10th and 90th percentile levels
    sorted_abs = sorted(abs(x) for x in signal)
    if sorted_abs:
        p10 = sorted_abs[int(0.1 * (len(sorted_abs) - 1))]
        p90 = sorted_abs[int(0.9 * (len(sorted_abs) - 1))]
        lra = abs(_lufs_from_rms(p90) - _lufs_from_rms(p10))
    else:
        lra = 0.0
    tp = _true_peak(signal)
    return LoudnessReport(integrated_lufs=integrated, loudness_range=lra, true_peak=tp)


def normalize(signal: List[float], sr: int, target_lufs: float = TARGET_LUFS) -> Tuple[List[float], LoudnessReport]:
    rms = _rms(signal)
    integrated = _lufs_from_rms(rms)
    if integrated == -float("inf"):
        gain = 1.0
    else:
        gain = 10 ** ((target_lufs - integrated) / 20.0)
    normalized = [max(-1.0, min(1.0, sample * gain)) for sample in signal]
    tp = _true_peak(normalized)
    if tp > TRUE_PEAK_LIMIT:
        delta = tp - TRUE_PEAK_LIMIT + 0.2
        gain *= 10 ** (-delta / 20.0)
        normalized = [max(-1.0, min(1.0, sample * 10 ** (-delta / 20.0))) for sample in normalized]
        tp = _true_peak(normalized)
    report = measure(normalized, sr)
    report.target_lufs = target_lufs
    return normalized, report


__all__ = ["LoudnessReport", "measure", "normalize", "TARGET_LUFS", "TRUE_PEAK_LIMIT"]
