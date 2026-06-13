"""Optional ML voice separation via Demucs (htdemucs)."""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_DEMUCS_MODEL = None


def demucs_available() -> bool:
    try:
        import demucs  # noqa: F401
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def demucs_status_message() -> str:
    if demucs_available():
        return "Demucs ready — stronger vocal isolation than HPSS"
    return "Install optional ML deps: pip install -r requirements-ml.txt"


def _load_model():
    global _DEMUCS_MODEL
    if _DEMUCS_MODEL is not None:
        return _DEMUCS_MODEL
    from demucs.pretrained import get_model

    _DEMUCS_MODEL = get_model("htdemucs")
    _DEMUCS_MODEL.eval()
    return _DEMUCS_MODEL


def isolate_voice_ml(x: np.ndarray, sr: int, amount: float = 0.7) -> np.ndarray:
    """
    Extract vocals with Demucs htdemucs. Falls back to HPSS on failure.

    First run downloads ~80 MB model weights. CPU inference is slow on long files.
    """
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount <= 0.01 or len(x) < sr // 10:
        return x.astype(np.float32, copy=False)

    if not demucs_available():
        from app.dsp.separation import isolate_voice

        return isolate_voice(x, sr, amount)

    try:
        import torch
        from demucs.apply import apply_model

        from app.dsp.separation import isolate_voice

        model = _load_model()
        model_sr = model.samplerate
        mono = x.astype(np.float32)
        if sr != model_sr:
            ratio = model_sr / sr
            new_len = max(1, int(len(mono) * ratio))
            resampled = np.interp(
                np.linspace(0, len(mono) - 1, new_len),
                np.arange(len(mono)),
                mono,
            ).astype(np.float32)
        else:
            resampled = mono

        wav = torch.from_numpy(resampled).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            sources = apply_model(model, wav, device="cpu", progress=False, num_workers=0)
        # htdemucs: drums, bass, other, vocals
        vocals = sources[3, 0].numpy().astype(np.float32)
        if len(vocals) != len(mono):
            vocals = np.interp(
                np.linspace(0, len(vocals) - 1, len(mono)),
                np.arange(len(vocals)),
                vocals,
            ).astype(np.float32)
        out = mono * (1.0 - amount) + vocals * amount
        return np.clip(out, -1.0, 1.0).astype(np.float32)
    except Exception as exc:
        logger.warning("Demucs failed, using HPSS fallback: %s", exc)
        from app.dsp.separation import isolate_voice

        return isolate_voice(x, sr, amount)


__all__ = ["demucs_available", "demucs_status_message", "isolate_voice_ml"]
