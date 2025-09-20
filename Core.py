#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core.py — DSP ядро для UnifyAudio
- Сегментация (voice/energy)
- Match-EQ с защитами и tilt
- Denoise, Dereverb (спектральный), Gate, Comp, De-esser, Saturation, Exciter
- Limiter + пост-LUFS + простая TruePeak защита
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
import soundfile as sf
from scipy.signal import stft, istft, butter, sosfilt, resample_poly
from scipy.fftpack import dct
import pyloudnorm as pyln

TARGET_SR = 48000
EPS = 1e-12

# ------------------------------
# IO
# ------------------------------
def read_audio_any(path: str):
    x, sr = sf.read(path, always_2d=False)
    if x.ndim == 2:
        x = (x[:, 0] + x[:, 1]) * 0.5
    return x.astype(np.float32, copy=False), int(sr)

def to_sr_mono(x: np.ndarray, sr: int, target: int = TARGET_SR):
    if sr != target:
        from math import gcd
        g = gcd(sr, target)
        up = target // g
        down = sr // g
        x = resample_poly(x, up, down).astype(np.float32)
        sr = target
    return x, sr

# ------------------------------
# Level utils
# ------------------------------
def loudnorm(x: np.ndarray, sr: int, target_lufs: float) -> np.ndarray:
    meter = pyln.Meter(sr, block_size=0.400, oversample=True)
    cur = meter.integrated_loudness(x)
    return pyln.normalize.loudness(x, cur, target_lufs).astype(np.float32)

# ------------------------------
# Basic filters
# ------------------------------
def hpf_80(x: np.ndarray, sr: int) -> np.ndarray:
    sos = butter(2, 80.0/(sr/2), btype='highpass', output='sos')
    return sosfilt(sos, x).astype(np.float32)

# ------------------------------
# Noise & Dereverb
# ------------------------------
def spectral_gate(x: np.ndarray, sr: int, frame_ms: float = 20.0, hop_ratio: float = 0.5,
                  reduction_db: float = 12.0, floor_db: float = -30.0) -> np.ndarray:
    win = int(sr * frame_ms / 1000)
    p = int(np.ceil(np.log2(max(256, win))))
    n_fft = 2 ** p
    hop = max(1, int(win * hop_ratio))
    window = np.hanning(win)
    _, _, Z = stft(x, fs=sr, window=window, nperseg=win, noverlap=win-hop, nfft=n_fft, boundary=None)
    mag = np.abs(Z)
    alpha = 0.95
    noise = np.copy(mag[:, :1]) + EPS
    for i in range(1, mag.shape[1]):
        noise = np.minimum(alpha * noise + (1 - alpha) * mag[:, i:i+1], mag[:, i:i+1])
    red_lin = 10 ** (-reduction_db / 20.0)
    floor_lin = 10 ** (floor_db / 20.0)
    thresh = noise * (1.0 / red_lin)
    M = np.where(mag >= thresh, 1.0, np.clip(mag / (thresh + EPS), floor_lin, 1.0))
    Y = M * Z
    _, y = istft(Y, fs=sr, window=window, nperseg=win, noverlap=win-hop, nfft=n_fft, input_onesided=True)
    return np.clip(y, -1.0, 1.0).astype(np.float32)

def dereverb_spectral(x: np.ndarray, sr: int, amount: float = 0.5) -> np.ndarray:
    """
    Простой «late-reverb suppression» без внешних зависимостей.
    Идея: в STFT оценивать «атакующую огибающую» (быстрый макс) и «хвост» (медленная средняя).
    Подавлять хвостовую компоненту, завися от amount [0..1].
    """
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount <= 0:
        return x.astype(np.float32)
    n_fft = 4096
    hop = n_fft // 4
    win = np.hanning(n_fft)
    _, _, Z = stft(x, fs=sr, window=win, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, boundary=None)
    mag = np.abs(Z) + EPS
    phase = np.angle(Z)

    # Быстрая «атака» и медленный «хвост»
    atk = np.copy(mag[:, :1])
    tail = np.copy(mag[:, :1])
    alpha_atk = 0.3   # быстрее
    alpha_tail = 0.98 # медленнее
    A = np.zeros_like(mag)
    T = np.zeros_like(mag)
    A[:, 0] = atk[:, 0]
    T[:, 0] = tail[:, 0]
    for t in range(1, mag.shape[1]):
        A[:, t] = np.maximum(alpha_atk * A[:, t-1], mag[:, t])
        T[:, t] = alpha_tail * T[:, t-1] + (1 - alpha_tail) * mag[:, t]

    # Отношение хвоста к атаке (tail > attack*k -> подавляем)
    r = (T / (A + EPS))
    # Маска подавления: плавная, зависимая от amount
    # больше подавления в ВЧ (где реверб заметнее)
    freqs = np.linspace(0, sr/2, mag.shape[0])
    hf_boost = np.clip((freqs - 1500.0) / 6000.0, 0.0, 1.0)  # 0..1 от 1.5к до 7.5к
    k = 0.6 + 0.4 * hf_boost  # порог чуть ниже в ВЧ
    # степень подавления
    suppr = np.clip((r - k) / (1.5 - k), 0.0, 1.0)
    depth_db = 12.0 * amount
    M = 10 ** (-(depth_db * suppr) / 20.0)

    Y = (mag * M) * np.exp(1j * phase)
    _, y = istft(Y, fs=sr, window=win, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, input_onesided=True)
    return np.clip(y, -1.0, 1.0).astype(np.float32)

# ------------------------------
# Spectral stats
# ------------------------------
def avg_mag_spectrum(x: np.ndarray, sr: int, n_fft: int = 4096, hop: Optional[int] = None) -> np.ndarray:
    if hop is None:
        hop = n_fft // 4
    window = np.hanning(n_fft)
    _, _, Z = stft(x, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, boundary=None)
    mag = np.abs(Z) + EPS
    avg = np.exp(np.mean(np.log(mag), axis=1))
    return avg

def smooth_log_freq_curve(curve: np.ndarray, sr: int, n_fft: int, bins_per_oct: int = 12) -> np.ndarray:
    freqs = np.linspace(0, sr/2, len(curve))
    curve_db = 20*np.log10(np.maximum(curve, EPS))
    fmin, fmax = 50.0, 12000.0
    centers = []
    f = fmin
    while f <= fmax:
        centers.append(f)
        f *= 2 ** (1.0/bins_per_oct)
    centers = np.array(centers)
    out_db = np.empty_like(curve_db)
    for i, fr in enumerate(freqs):
        idx = np.argmin(np.abs(centers - fr))
        if idx == 0:
            bw = (centers[1] - centers[0]) * 0.5
        else:
            bw = (centers[min(idx+1, len(centers)-1)] - centers[idx-1]) * 0.25
        lo, hi = fr - bw, fr + bw
        mask = (freqs >= lo) & (freqs <= hi)
        out_db[i] = np.mean(curve_db[mask]) if np.any(mask) else curve_db[i]
    return 10 ** (out_db / 20.0)

def compute_match_filter(ref_avg: np.ndarray, cur_avg: np.ndarray, sr: int, n_fft: int,
                         max_gain_db: float = 6.0,
                         weight: float = 1.0,
                         bass_guard_hz: float = 140.0,
                         bass_guard_max_boost_db: float = 1.5,
                         tilt_db_per_oct: float = 0.0) -> np.ndarray:
    ratio = (ref_avg + EPS) / (cur_avg + EPS)
    ratio = smooth_log_freq_curve(ratio, sr, n_fft, bins_per_oct=12)
    ratio_db = 20*np.log10(np.maximum(ratio, EPS))

    # Tilt вокруг 1 кГц
    freqs = np.linspace(0.0, sr/2.0, len(ratio_db))
    safe_freqs = np.maximum(freqs, 1.0)
    ratio_db = ratio_db + float(tilt_db_per_oct) * np.log2(safe_freqs / 1000.0)

    # Вес
    ratio_db = ratio_db * float(np.clip(weight, 0.0, 1.0))

    # Bass guard
    if bass_guard_hz is not None and bass_guard_max_boost_db is not None:
        idx = freqs <= float(bass_guard_hz)
        ratio_db[idx] = np.where(
            ratio_db[idx] > 0.0,
            np.minimum(ratio_db[idx], float(bass_guard_max_boost_db)),
            ratio_db[idx]
        )

    ratio_db = np.clip(ratio_db, -float(max_gain_db), float(max_gain_db))
    H = 10 ** (ratio_db / 20.0)
    H[0] = 1.0
    return H.astype(np.float32)

def apply_static_match_eq(x: np.ndarray, sr: int, H: np.ndarray, n_fft: int = 4096) -> np.ndarray:
    hop = n_fft // 4
    window = np.hanning(n_fft)
    _, _, Z = stft(x, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, boundary=None)
    Y = Z * H[:, None]
    _, y = istft(Y, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, input_onesided=True)
    return np.clip(y, -1.0, 1.0).astype(np.float32)

# ------------------------------
# Dynamics & FX
# ------------------------------
def compressor(x: np.ndarray, sr: int, thresh_db: float=-24.0, ratio: float=2.5,
               attack_ms: float=15.0, release_ms: float=90.0, makeup_db: float=0.0, knee_db: float=6.0) -> np.ndarray:
    import math
    attack = int(sr * attack_ms / 1000.0)
    release = int(sr * release_ms / 1000.0)
    win = max(1, int(sr * 0.020))
    pad = win // 2
    x_pad = np.pad(x, (pad, pad), mode='reflect')
    rms = np.sqrt(np.convolve(x_pad**2, np.ones(win)/win, mode='valid') + EPS)
    lvl_db = 20*np.log10(rms + EPS)

    gain_db = np.zeros_like(lvl_db)
    for i, ld in enumerate(lvl_db):
        over = ld - thresh_db
        if over <= -knee_db/2:
            gd = 0.0
        elif over >= knee_db/2:
            gd = (1 - 1/ratio) * over
        else:
            t = (over + knee_db/2)/knee_db
            gd = (1 - 1/ratio) * (t**2) * knee_db/2
        gain_db[i] = -gd

    alpha_a = math.exp(-1.0 / max(1, attack))
    alpha_r = math.exp(-1.0 / max(1, release))
    sm = np.zeros_like(gain_db)
    prev = 0.0
    for i, g in enumerate(gain_db):
        if g < prev:
            prev = alpha_a * prev + (1 - alpha_a) * g
        else:
            prev = alpha_r * prev + (1 - alpha_r) * g
        sm[i] = prev

    gain = 10 ** ((sm + makeup_db)/20.0)
    return (x * gain[:len(x)]).astype(np.float32)

def hysteresis_gate(x: np.ndarray, sr: int, open_db: float=-45.0, close_db: float=-50.0, ratio: float=1.5) -> np.ndarray:
    win = max(1, int(sr * 0.020))
    env = np.sqrt(np.convolve(np.pad(x**2, (win//2, win//2), mode='reflect'), np.ones(win)/win, mode='valid') + EPS)
    env_db = 20*np.log10(env + EPS)
    state_open = False
    g_db = np.zeros_like(env_db)
    for i, edb in enumerate(env_db):
        if state_open:
            if edb < close_db:
                state_open = False
        else:
            if edb > open_db:
                state_open = True
        if state_open:
            g_db[i] = 0.0
        else:
            g_db[i] = min(0.0, (close_db - edb) * (1 - 1/ratio)) * -1.0
    gain = 10 ** (g_db / 20.0)
    return (x * gain[:len(x)]).astype(np.float32)

def soft_saturate(x: np.ndarray, drive_db: float=0.0, mix: float=0.2) -> np.ndarray:
    if drive_db <= 0 or mix <= 0:
        return x.astype(np.float32)
    drive = 10 ** (drive_db/20.0)
    y = np.tanh(drive * x)
    return np.clip((1-mix)*x + mix*y, -1.0, 1.0).astype(np.float32)

def high_band_exciter(x: np.ndarray, sr: int, fc: float=4000.0, amount: float=0.0) -> np.ndarray:
    if amount <= 0:
        return x.astype(np.float32)
    sos = butter(2, fc/(sr/2), btype='highpass', output='sos')
    h = sosfilt(sos, x)
    h = np.tanh(3.0 * h)
    return np.clip(x + amount * h, -1.0, 1.0).astype(np.float32)

def limiter(x: np.ndarray, sr: int, ceiling_db: float=-1.0, lookahead_ms: float=3.0, release_ms: float=50.0) -> np.ndarray:
    import math
    look = int(sr * lookahead_ms / 1000.0)
    rel = int(sr * release_ms / 1000.0)
    pad = np.pad(x, (look, 0))
    env = np.maximum.accumulate(np.abs(pad))
    env = np.maximum(env, EPS)
    ceiling = 10 ** (ceiling_db / 20.0)
    gain = np.minimum(1.0, ceiling / env)
    alpha = math.exp(-1.0 / max(1, rel))
    for i in range(1, len(gain)):
        if gain[i] > gain[i-1]:
            gain[i] = alpha * gain[i-1] + (1 - alpha) * gain[i]
    y = pad * gain
    return y[look:look+len(x)].astype(np.float32)

def truepeak_limit(x: np.ndarray, sr: int, ceiling_db: float=-1.0, oversample: int = 4) -> np.ndarray:
    """
    Простая защита по true-peak: оцениваем пик на oversample и скейлим сигнал.
    Это не динамический лимитер, но надёжно убирает интерсэмпловые превышения.
    """
    if oversample < 2:
        oversample = 2
    up = oversample
    # oversample
    x_os = resample_poly(x, up, 1).astype(np.float32)
    peak = float(np.max(np.abs(x_os)) + EPS)
    ceiling = 10 ** (ceiling_db / 20.0)
    if peak <= ceiling:
        return x.astype(np.float32)
    gain = ceiling / peak
    return (x * gain).astype(np.float32)

# ------------------------------
# Quality metrics & concat
# ------------------------------
def estimate_snr(x: np.ndarray, sr: int) -> float:
    n_fft = 1024
    hop = n_fft // 2
    window = np.hanning(n_fft)
    _, _, Z = stft(x, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, boundary=None)
    p = np.mean(np.abs(Z)**2, axis=0)
    thr = np.percentile(p, 25)
    noise = np.mean(p[p <= thr]) + EPS
    voice = np.mean(p[p > thr]) + EPS
    return float(10 * np.log10(voice / noise))

def crossfade_concat(chunks: List[np.ndarray], sr: int, xf_ms: float = 10.0) -> np.ndarray:
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    out = chunks[0].astype(np.float32)
    xf = int(sr * xf_ms / 1000.0)
    for chunk in chunks[1:]:
        a = out
        b = chunk.astype(np.float32)
        if xf > 0 and len(a) > xf and len(b) > xf:
            w = np.linspace(0, 1, xf, dtype=np.float32)
            tail = a[-xf:] * (1 - w) + b[:xf] * w
            out = np.concatenate([a[:-xf], tail, b[xf:]], axis=0)
        else:
            out = np.concatenate([a, b], axis=0)
    return np.clip(out, -1.0, 1.0)

# ------------------------------
# Segmentation
# ------------------------------
def detect_segments(x: np.ndarray, sr: int,
                    min_seg_s: float = 6.0,
                    block_s: float = 2.0,
                    hop_s: float = 1.0,
                    sensitivity: float = 1.0,
                    mode: str = "voice") -> List[Tuple[int, int]]:
    mode = (mode or "voice").lower()
    if mode == "energy":
        return detect_segments_energy(x, sr, min_seg_s, block_s, hop_s, sensitivity)
    else:
        return detect_segments_voice_change(x, sr, min_seg_s, block_s, hop_s, sensitivity)

def detect_segments_energy(x: np.ndarray, sr: int,
                           min_seg_s: float, block_s: float, hop_s: float, sensitivity: float) -> List[Tuple[int, int]]:
    n = len(x)
    if n == 0 or sr <= 0:
        return []
    block = max(1, int(block_s * sr))
    hop = max(1, int(hop_s * sr))
    idxs = list(range(0, max(1, n - block + 1), hop))
    if not idxs:
        return [(0, n)]
    rms = []
    for i in idxs:
        w = x[i:i+block]
        rms.append(20.0 * np.log10(np.sqrt(np.mean(w*w) + EPS) + EPS))
    rms = np.asarray(rms, dtype=np.float32)
    if len(rms) >= 5:
        rms = np.convolve(rms, np.ones(5)/5.0, mode='same')
    p10 = float(np.percentile(rms, 10))
    p90 = float(np.percentile(rms, 90))
    thr = p10 + float(sensitivity) * (p90 - p10) * 0.25
    active = rms > thr
    if len(active) >= 3:
        kernel = np.ones(3, dtype=np.int32)
        active = np.convolve(active.astype(np.int32), kernel, mode='same') > 0
    min_len = int(min_seg_s * sr)
    merge_gap = int(0.6 * sr)

    segs: List[Tuple[int, int]] = []
    in_seg = False
    start_i = 0
    for k, flag in enumerate(active):
        if flag and not in_seg:
            in_seg = True; start_i = k
        elif not flag and in_seg:
            in_seg = False
            a = idxs[start_i]
            b = min(n, idxs[k] + block)
            if segs and (a - segs[-1][1]) <= merge_gap: segs[-1] = (segs[-1][0], b)
            else:
                if (b - a) >= min_len: segs.append((a, b))
    if in_seg:
        a = idxs[start_i]; b = n
        if segs and (a - segs[-1][1]) <= merge_gap: segs[-1] = (segs[-1][0], b)
        else:
            if (b - a) >= min_len: segs.append((a, b))
    if not segs: segs = [(0, n)]
    return segs

def detect_segments_voice_change(x: np.ndarray, sr: int,
                                 min_seg_s: float, block_s: float, hop_s: float, sensitivity: float) -> List[Tuple[int, int]]:
    n = len(x)
    if n == 0 or sr <= 0:
        return []
    block = max(1, int(block_s * sr))
    hop = max(1, int(hop_s * sr))
    centers = []
    feats = []
    n_fft = 1
    while n_fft < block: n_fft <<= 1
    window = np.hanning(block).astype(np.float32)
    for start in range(0, max(1, n - block + 1), hop):
        w = x[start:start+block]
        if len(w) < block: w = np.pad(w, (0, block - len(w)))
        W = np.fft.rfft(w * window, n=n_fft)
        mag = np.abs(W).astype(np.float32) + EPS
        logmag = np.log(mag)
        cep = dct(logmag, type=2, norm='ortho')[:13]
        feats.append(cep); centers.append(start + block//2)
    if len(feats) < 3:
        return [(0, n)]
    F = np.asarray(feats, dtype=np.float32)
    norms = np.linalg.norm(F, axis=1, keepdims=True) + EPS
    Fn = F / norms
    d = 1.0 - np.sum(Fn[1:] * Fn[:-1], axis=1)
    if len(d) >= 5:
        d = np.convolve(d, np.ones(5)/5.0, mode='same')
    med = float(np.median(d)); p90 = float(np.percentile(d, 90))
    thr = max(med * 1.05, med + float(sensitivity) * 0.5 * (p90 - med))
    peaks = []
    rad = 2
    for i in range(1, len(d)-1):
        if d[i] > thr and d[i] == max(d[max(0, i-rad):min(len(d), i+rad+1)]):
            peaks.append(i)
    cuts = [centers[i] for i in peaks]
    min_len = int(min_seg_s * sr)
    cuts = [c for c in cuts if min_len <= c <= (n - min_len)]
    cuts_sorted: List[int] = []
    for c in sorted(cuts):
        if not cuts_sorted or (c - cuts_sorted[-1]) >= min_len:
            cuts_sorted.append(c)
    segs = []
    prev = 0
    for c in cuts_sorted:
        segs.append((prev, c)); prev = c
    segs.append((prev, n))
    segs = [(a, b) for (a, b) in segs if (b - a) >= min_len]
    if not segs: segs = [(0, n)]
    return segs

# ------------------------------
# Params & main pipeline
# ------------------------------
@dataclass
class ProcParams:
    # Loudness targets
    pre_lufs: float = -23.0
    post_lufs: float = -19.0
    # Denoise
    denoise: bool = True
    denoise_reduction_db: float = 12.0
    # Dereverb
    dereverb_enable: bool = False
    dereverb_amount: float = 0.5
    # Match-EQ
    eq_max_gain_db: float = 6.0
    eq_match_weight: float = 1.0
    tilt_db_per_oct: float = 0.0
    bass_guard_hz: float = 140.0
    bass_guard_max_boost_db: float = 1.5
    # Dynamics
    comp_thresh_db: float = -24.0
    comp_ratio: float = 2.5
    comp_attack_ms: float = 15.0
    comp_release_ms: float = 90.0
    comp_makeup_db: float = 0.0
    # Gate
    gate_enable: bool = False
    gate_open_db: float = -45.0
    gate_close_db: float = -50.0
    gate_ratio: float = 1.5
    # Sibilance
    deess_amount_db: float = 6.0
    # Color
    sat_drive_db: float = 0.0
    sat_mix: float = 0.2
    exciter_amount: float = 0.0
    exciter_fc: float = 4000.0
    # Output ceiling
    limiter_ceiling_db: float = -1.0
    limiter_truepeak: bool = True

def process_signal(x: np.ndarray, sr: int, H_match: Optional[np.ndarray], p: ProcParams) -> np.ndarray:
    # ВНИМАНИЕ: вызывать ПОСЛЕ сегментации. Здесь обрабатывается один сегмент.
    x, sr = to_sr_mono(x, sr, TARGET_SR)
    try:
        x = loudnorm(x, sr, p.pre_lufs)
    except Exception:
        pass

    x = hpf_80(x, sr)
    if p.denoise:
        x = spectral_gate(x, sr, reduction_db=p.denoise_reduction_db)
    if p.dereverb_enable and p.dereverb_amount > 0:
        x = dereverb_spectral(x, sr, amount=p.dereverb_amount)

    if H_match is not None:
        x = apply_static_match_eq(x, sr, H_match)

    if p.gate_enable:
        x = hysteresis_gate(x, sr, p.gate_open_db, p.gate_close_db, p.gate_ratio)

    x = compressor(x, sr, p.comp_thresh_db, p.comp_ratio, p.comp_attack_ms, p.comp_release_ms, p.comp_makeup_db)

    if p.deess_amount_db > 0:
        n_fft = 2048; hop = n_fft//4; window = np.hanning(n_fft)
        f, t, Z = stft(x, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, boundary=None)
        mag = np.abs(Z); phase = np.angle(Z)
        idx = (f >= 5000.0) & (f <= 10000.0)
        band_e = np.mean(mag[idx, :], axis=0) + EPS
        wide_e = np.mean(mag, axis=0) + EPS
        ratio = band_e / wide_e
        atten_db = np.clip((ratio - 1.0) * p.deess_amount_db, 0.0, p.deess_amount_db)
        atten = 10 ** (-atten_db / 20.0)
        M = np.ones_like(mag); M[idx, :] *= atten[None, :]
        Y = (mag * M) * np.exp(1j * phase)
        _, x = istft(Y, fs=sr, window=window, nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, input_onesided=True)

    if p.sat_drive_db > 0:
        x = soft_saturate(x, p.sat_drive_db, p.sat_mix)
    if p.exciter_amount > 0:
        x = high_band_exciter(x, sr, p.exciter_fc, p.exciter_amount)

    x = limiter(x, sr, ceiling_db=p.limiter_ceiling_db)

    try:
        x = loudnorm(x, sr, p.post_lufs)
    except Exception:
        pass

    if p.limiter_truepeak:
        x = truepeak_limit(x, sr, ceiling_db=p.limiter_ceiling_db, oversample=4)

    return np.clip(x, -1.0, 1.0).astype(np.float32)