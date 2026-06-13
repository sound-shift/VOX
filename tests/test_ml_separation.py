from __future__ import annotations

import numpy as np

from app.dsp.ml_separation import demucs_available, demucs_status_message, isolate_voice_ml


def test_demucs_status_returns_string():
    msg = demucs_status_message()
    assert isinstance(msg, str)
    assert len(msg) > 10


def test_isolate_voice_ml_fallback_without_demucs(monkeypatch):
    monkeypatch.setattr("app.dsp.ml_separation.demucs_available", lambda: False)
    sr = 48000
    x = np.sin(np.linspace(0, 4 * np.pi, sr)).astype(np.float32) * 0.2
    out = isolate_voice_ml(x, sr, amount=0.5)
    assert out.shape == x.shape
