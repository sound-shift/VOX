"""Magic and advanced processing chains implemented with lightweight helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import math

from app.dsp import loudness
from app.dsp.presets import VoicePreset, get_preset


@dataclass
class AdvancedParams:
    tilt_db_per_oct: float
    presence_gain_db: float
    presence_range: tuple[float, float]
    denoise_amount: float
    dereverb_amount: float
    gate_threshold: float
    saturation: float

    @classmethod
    def from_preset(cls, preset: VoicePreset) -> "AdvancedParams":
        return cls(
            tilt_db_per_oct=preset.tilt_db_per_oct,
            presence_gain_db=preset.presence_gain_db,
            presence_range=preset.presence_range,
            denoise_amount=0.35,
            dereverb_amount=0.25,
            gate_threshold=-48.0,
            saturation=0.1,
        )


@dataclass
class MagicResult:
    processed: List[float]
    report: loudness.LoudnessReport
    metadata: Dict[str, float]


def _apply_gain_envelope(signal: List[float], envelope: List[float]) -> List[float]:
    return [sample * gain for sample, gain in zip(signal, envelope)]


def _tilt(signal: List[float], tilt_db_per_oct: float) -> List[float]:
    if not signal:
        return []
    length = len(signal)
    envelope: List[float] = []
    for i in range(length):
        t = i / max(1, length - 1)
        gain_db = tilt_db_per_oct * (t - 0.5) * 2.0
        envelope.append(10 ** (gain_db / 20.0))
    return _apply_gain_envelope(signal, envelope)


def _presence(signal: List[float], gain_db: float) -> List[float]:
    factor = 10 ** (gain_db / 20.0)
    smoothed: List[float] = []
    prev = 0.0
    for sample in signal:
        prev = 0.6 * prev + 0.4 * sample
        smoothed.append(sample + (sample - prev) * (factor - 1.0))
    return smoothed


def _denoise(signal: List[float], amount: float) -> List[float]:
    amount = max(0.0, min(1.0, amount))
    if amount <= 0.0:
        return list(signal)
    threshold = 0.02 * (1.0 + amount)
    return [sample * (1.0 - amount) if abs(sample) < threshold else sample for sample in signal]


def _dereverb(signal: List[float], amount: float) -> List[float]:
    amount = max(0.0, min(1.0, amount))
    if amount <= 0.0:
        return list(signal)
    out: List[float] = []
    prev = 0.0
    alpha = 0.9 - amount * 0.4
    for sample in signal:
        prev = alpha * prev + (1 - alpha) * sample
        out.append(sample - prev * amount)
    return out


def _gate(signal: List[float], threshold_db: float) -> List[float]:
    threshold = 10 ** (threshold_db / 20.0)
    return [sample if abs(sample) >= threshold else 0.0 for sample in signal]


def _saturate(signal: List[float], amount: float) -> List[float]:
    amount = max(0.0, min(1.0, amount))
    if amount <= 0.0:
        return list(signal)
    gain = 1.0 + amount * 3.0
    return [math.tanh(sample * gain) for sample in signal]


def process_magic(signal: List[float], sr: int, preset_key: str, reference: Optional[List[float]] = None) -> MagicResult:
    preset = get_preset(preset_key)
    params = AdvancedParams.from_preset(preset)
    processed = _run_chain(signal, params)
    normalized, report = loudness.normalize(processed, sr)
    metadata = {
        "preset": preset.name,
        "tilt_db_per_oct": params.tilt_db_per_oct,
        "presence_gain_db": params.presence_gain_db,
        "denoise_amount": params.denoise_amount,
        "dereverb_amount": params.dereverb_amount,
        "saturation": params.saturation,
    }
    return MagicResult(processed=normalized, report=report, metadata=metadata)


def process_advanced(signal: List[float], sr: int, params: AdvancedParams) -> MagicResult:
    processed = _run_chain(signal, params)
    normalized, report = loudness.normalize(processed, sr)
    metadata = {
        "tilt_db_per_oct": params.tilt_db_per_oct,
        "presence_gain_db": params.presence_gain_db,
        "denoise_amount": params.denoise_amount,
        "dereverb_amount": params.dereverb_amount,
        "saturation": params.saturation,
    }
    return MagicResult(processed=normalized, report=report, metadata=metadata)


def _run_chain(signal: List[float], params: AdvancedParams) -> List[float]:
    x = list(signal)
    x = _denoise(x, params.denoise_amount)
    x = _dereverb(x, params.dereverb_amount)
    x = _gate(x, params.gate_threshold)
    x = _tilt(x, params.tilt_db_per_oct)
    x = _presence(x, params.presence_gain_db)
    x = _saturate(x, params.saturation)
    return [max(-1.0, min(1.0, sample)) for sample in x]


__all__ = [
    "AdvancedParams",
    "MagicResult",
    "process_magic",
    "process_advanced",
]
