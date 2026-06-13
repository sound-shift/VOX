"""Captured noise profile for profile-aware denoising."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from scipy.signal import istft, stft

from app.legacy.unify.core import EPS, avg_mag_spectrum


@dataclass
class NoiseProfile:
    magnitude: List[float]
    sr: int
    n_fft: int = 2048
    duration_sec: float = 0.0

    @classmethod
    def capture(cls, samples: List[float] | np.ndarray, sr: int, n_fft: int = 2048) -> "NoiseProfile":
        x = np.asarray(samples, dtype=np.float32)
        if x.size < max(64, sr // 50):
            raise ValueError("Noise sample too short — need at least ~0.02 s of audio")
        mag = avg_mag_spectrum(x, sr, n_fft=n_fft)
        return cls(
            magnitude=mag.astype(float).tolist(),
            sr=int(sr),
            n_fft=n_fft,
            duration_sec=float(x.size / sr),
        )

    def to_dict(self) -> dict:
        return {
            "magnitude": self.magnitude,
            "sr": self.sr,
            "n_fft": self.n_fft,
            "duration_sec": self.duration_sec,
        }

    @classmethod
    def from_dict(cls, payload: Optional[dict]) -> Optional["NoiseProfile"]:
        if not payload or not payload.get("magnitude"):
            return None
        return cls(
            magnitude=list(payload["magnitude"]),
            sr=int(payload.get("sr", 48000)),
            n_fft=int(payload.get("n_fft", 2048)),
            duration_sec=float(payload.get("duration_sec", 0.0)),
        )


def apply_noise_reduction(
    x: np.ndarray,
    sr: int,
    profile: NoiseProfile,
    *,
    reduction_db: float = 12.0,
    floor_db: float = -42.0,
    sensitivity: float = 0.65,
) -> np.ndarray:
    """Spectral denoise using a captured noise magnitude profile."""
    if profile.sr != sr:
        raise ValueError("Noise profile sample rate does not match audio")

    n_fft = profile.n_fft
    hop = n_fft // 4
    window = np.hanning(n_fft)
    _, _, z = stft(x, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft - hop, nfft=n_fft, boundary=None)
    mag = np.abs(z)
    phase = np.angle(z)

    noise = np.asarray(profile.magnitude, dtype=np.float32)
    if noise.shape[0] != mag.shape[0]:
        src = np.linspace(0, 1, noise.shape[0])
        dst = np.linspace(0, 1, mag.shape[0])
        noise = np.interp(dst, src, noise).astype(np.float32)

    sens = float(np.clip(sensitivity, 0.05, 1.0))
    thresh = noise * (0.5 + sens * 1.5)
    red_lin = 10 ** (-float(reduction_db) / 20.0)
    floor_lin = 10 ** (float(floor_db) / 20.0)

    mask = np.ones_like(mag)
    over = mag > thresh[:, None]
    below = np.clip(mag / (thresh[:, None] + EPS), floor_lin, 1.0)
    mask = np.where(over, 1.0, np.maximum(red_lin, below))

    y = istft(mask * mag * np.exp(1j * phase), fs=sr, window=window, nperseg=n_fft, noverlap=n_fft - hop, nfft=n_fft)[1]
    if len(y) < len(x):
        y = np.pad(y, (0, len(x) - len(y)))
    elif len(y) > len(x):
        y = y[: len(x)]
    return np.clip(y, -1.0, 1.0).astype(np.float32)


__all__ = ["NoiseProfile", "apply_noise_reduction"]
