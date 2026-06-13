from __future__ import annotations

import math

import numpy as np

from app.dsp.noise_profile import NoiseProfile, apply_noise_reduction
from app.dsp.pipeline import ProcessingOptions, process_take
from app.dsp.presets import get_preset
from app.dsp.workflows import get_workflow


def test_adr_preset_exists():
    preset = get_preset("adr_dialog")
    assert "ADR" in preset.name


def test_adr_workflow_defaults():
    wf = get_workflow("adr")
    assert wf.preset_key == "adr_dialog"
    assert wf.gate_enable is True
    assert wf.denoise_db >= 14


def test_noise_profile_capture_and_apply():
    sr = 48000
    noise = np.random.randn(sr).astype(np.float32) * 0.01
    profile = NoiseProfile.capture(noise[: sr // 4].tolist(), sr)
    assert profile.duration_sec > 0

    signal = noise + 0.05 * np.sin(2 * math.pi * 440 * np.arange(sr) / sr).astype(np.float32)
    cleaned = apply_noise_reduction(signal, sr, profile, reduction_db=12, floor_db=-40, sensitivity=0.6)
    assert len(cleaned) == len(signal)


def test_pipeline_with_noise_profile():
    sr = 48000
    noise = [0.01 * (i % 7 - 3) for i in range(sr)]
    profile = NoiseProfile.capture(noise, sr)
    signal = [0.08 * math.sin(2 * math.pi * 220 * i / sr) + 0.01 for i in range(sr)]
    opts = ProcessingOptions(
        preset_key="adr_dialog",
        noise_profile=profile,
        use_noise_profile=True,
        denoise_reduction_db=14,
        denoise_floor_db=-40,
        denoise_sensitivity=0.6,
        match_weight=0.0,
    )
    result = process_take(signal, sr, opts)
    assert len(result.processed) == len(signal)
    assert result.metadata.get("noise_profile") == 1.0
