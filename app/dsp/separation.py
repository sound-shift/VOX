"""Voice isolation from mixed beds (music / foley / dialog)."""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, stft, istft


def _hpss(mag: np.ndarray, kernel: int = 31) -> tuple[np.ndarray, np.ndarray]:
    """Harmonic-percussive magnitude separation (median filtering)."""
    from scipy.ndimage import median_filter

    k = max(3, kernel | 1)
    harmonic = median_filter(mag, size=(1, k))
    percussive = median_filter(mag, size=(k, 1))
    total = harmonic + percussive + 1e-12
    h_ratio = harmonic / total
    p_ratio = percussive / total
    return mag * h_ratio, mag * p_ratio


def isolate_voice(x: np.ndarray, sr: int, amount: float = 0.7) -> np.ndarray:
    """
    Reduce non-vocal content using HPSS + vocal-band masking.

    ``amount`` 0..1 — strength of isolation (practical heuristic, not ML).
    """
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount <= 0.01 or len(x) < sr // 10:
        return x.astype(np.float32, copy=False)

    n_fft = 2048
    hop = n_fft // 4
    window = np.hanning(n_fft)
    _, _, z = stft(x, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft - hop, nfft=n_fft, boundary=None)
    mag = np.abs(z)
    phase = np.angle(z)
    harmonic, percussive = _hpss(mag)

    freqs = np.linspace(0, sr / 2, mag.shape[0])
    vocal_band = (freqs >= 180.0) & (freqs <= 4500.0)
    speech_band = (freqs >= 300.0) & (freqs <= 3400.0)

    vocal_mask = np.zeros_like(mag)
    vocal_mask[vocal_band, :] = 1.0
    vocal_mask[speech_band, :] = 1.35
    vocal_mask = np.clip(vocal_mask, 0.0, 1.5)

    # Favor harmonics (voice) over percussive (foley/transients)
    h_weight = 0.55 + 0.35 * amount
    p_weight = max(0.05, 0.45 - 0.35 * amount)
    combined = harmonic * h_weight + percussive * p_weight
    masked = combined * vocal_mask

    # Soft mix with original
    out_mag = mag * (1.0 - amount) + masked * amount
    y = istft(out_mag * np.exp(1j * phase), fs=sr, window=window, nperseg=n_fft, noverlap=n_fft - hop, nfft=n_fft)[1]
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))
    elif len(y) > len(x):
        y = y[: len(x)]
    y = np.clip(y, -1.0, 1.0).astype(np.float32)

    # High-pass rumble + de-mud
    sos = butter(2, 90.0 / (sr / 2), btype="highpass", output="sos")
    y = sosfilt(sos, y).astype(np.float32)
    return y


__all__ = ["isolate_voice"]
