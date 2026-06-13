"""Full processing pipeline — Unify DSP + match-EQ + isolation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.audio.media_io import read_audio_mono
from app.dsp import loudness
from app.dsp.noise_profile import NoiseProfile, apply_noise_reduction
from app.dsp.presets import VoicePreset, get_preset
from app.dsp.separation import isolate_voice
from app.legacy.unify.core import (
    ProcParams,
    apply_static_match_eq,
    avg_mag_spectrum,
    compute_match_filter,
    process_signal,
    to_sr_mono,
)


@dataclass
class ProcessingOptions:
    preset_key: str = "male_low"
    reference_path: Optional[Path] = None
    match_weight: float = 1.0
    tilt_db_per_oct: Optional[float] = None
    isolation_amount: float = 0.0
    denoise_reduction_db: float = 12.0
    denoise_floor_db: float = -36.0
    denoise_sensitivity: float = 0.5
    noise_profile: Optional[NoiseProfile] = None
    use_noise_profile: bool = True
    dereverb_amount: float = 0.35
    gate_enable: bool = False
    bypass: bool = False


@dataclass
class ProcessResult:
    processed: List[float]
    report: loudness.LoudnessReport
    metadata: Dict[str, float]


def preset_to_params(preset: VoicePreset, opts: ProcessingOptions) -> ProcParams:
    tilt = opts.tilt_db_per_oct if opts.tilt_db_per_oct is not None else preset.tilt_db_per_oct
    return ProcParams(
        pre_lufs=-23.0,
        post_lufs=-23.0,
        denoise=True,
        denoise_reduction_db=opts.denoise_reduction_db,
        dereverb_enable=opts.dereverb_amount > 0.05,
        dereverb_amount=float(np.clip(opts.dereverb_amount, 0.0, 1.0)),
        eq_max_gain_db=6.0,
        eq_match_weight=float(np.clip(opts.match_weight, 0.0, 1.0)),
        tilt_db_per_oct=tilt,
        bass_guard_hz=preset.low_guard_hz,
        bass_guard_max_boost_db=max(0.5, preset.low_shelf_gain_db + 1.0),
        gate_enable=opts.gate_enable,
        gate_open_db=-45.0,
        gate_close_db=-50.0,
        deess_amount_db=4.0 if preset.deesser_range else 2.0,
        sat_drive_db=2.0,
        sat_mix=0.15,
        exciter_amount=0.08,
        limiter_ceiling_db=-1.0,
        limiter_truepeak=True,
    )


def _build_match_filter(
    signal: np.ndarray,
    sr: int,
    reference_path: Path,
    params: ProcParams,
) -> Optional[np.ndarray]:
    ref_samples, ref_sr = read_audio_mono(reference_path, sr)
    ref_x = np.asarray(ref_samples, dtype=np.float32)
    ref_x, ref_sr = to_sr_mono(ref_x, ref_sr, sr)
    x, sr = to_sr_mono(signal, sr, sr)
    n_fft = 4096
    ref_avg = avg_mag_spectrum(ref_x, ref_sr, n_fft=n_fft)
    cur_avg = avg_mag_spectrum(x, sr, n_fft=n_fft)
    return compute_match_filter(
        ref_avg,
        cur_avg,
        sr,
        n_fft,
        max_gain_db=params.eq_max_gain_db,
        weight=params.eq_match_weight,
        bass_guard_hz=params.bass_guard_hz,
        bass_guard_max_boost_db=params.bass_guard_max_boost_db,
        tilt_db_per_oct=params.tilt_db_per_oct,
    )


def process_take(signal: List[float], sr: int, opts: ProcessingOptions) -> ProcessResult:
    if opts.bypass or not signal:
        normalized, report = loudness.normalize(list(signal), sr)
        return ProcessResult(processed=normalized, report=report, metadata={"bypass": 1.0})

    preset = get_preset(opts.preset_key)
    params = preset_to_params(preset, opts)
    x = np.asarray(signal, dtype=np.float32)
    x, sr = to_sr_mono(x, sr)

    if opts.isolation_amount > 0.01:
        x = isolate_voice(x, sr, opts.isolation_amount)

    used_profile = False
    if opts.noise_profile and opts.use_noise_profile:
        try:
            x = apply_noise_reduction(
                x,
                sr,
                opts.noise_profile,
                reduction_db=opts.denoise_reduction_db,
                floor_db=opts.denoise_floor_db,
                sensitivity=opts.denoise_sensitivity,
            )
            used_profile = True
            params.denoise = False
        except Exception:
            used_profile = False

    h_match: Optional[np.ndarray] = None
    if opts.reference_path and Path(opts.reference_path).exists() and params.eq_match_weight > 0.01:
        try:
            h_match = _build_match_filter(x, sr, Path(opts.reference_path), params)
        except Exception:
            h_match = None

    y = process_signal(x, sr, h_match, params)
    if len(y) != len(x):
        if len(y) > len(x):
            y = y[: len(x)]
        else:
            y = np.pad(y, (0, len(x) - len(y)))
    processed, report = loudness.normalize(y.tolist(), sr)

    metadata = {
        "preset": preset.name,
        "match_weight": params.eq_match_weight,
        "tilt_db_per_oct": params.tilt_db_per_oct,
        "isolation": opts.isolation_amount,
        "dereverb": params.dereverb_amount,
        "denoise_db": params.denoise_reduction_db,
        "noise_profile": 1.0 if used_profile else 0.0,
    }
    return ProcessResult(processed=processed, report=report, metadata=metadata)


__all__ = ["ProcessingOptions", "ProcessResult", "process_take", "preset_to_params"]
