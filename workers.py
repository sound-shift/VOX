# -*- coding: utf-8 -*-
"""
workers.py — segmentation workers for UnifyAudio
r9.4.4:
- Режим "silence": устойчивый по RMS-паузам
- Фолбэк: если разрывов не найдено, режем хотя бы через Min(s)
"""
from __future__ import annotations
import numpy as np
from typing import List, Tuple

from PySide6 import QtCore


class SegWorker(QtCore.QObject):
    done = QtCore.Signal(list)  # list of (a,b) sample indices
    error = QtCore.Signal(str)

    def __init__(self, x: np.ndarray, sr: int, min_seg_s: float = 6.0, sensitivity: float = 1.0, mode: str = "silence"):
        super().__init__()
        self.x = x.astype(np.float32)
        self.sr = int(sr)
        self.min_seg_s = float(min_seg_s)
        self.sensitivity = float(sensitivity)
        self.mode = mode

    @QtCore.Slot()
    def run(self):
        try:
            if len(self.x) < int(0.5 * self.sr):
                self.done.emit([(0, len(self.x))]); return

            if self.mode == "energy":
                cps = detect_change_points_energy(self.x, self.sr, sensitivity=self.sensitivity)
            elif self.mode == "emb":
                cps = detect_change_points_embeddings(self.x, self.sr, sensitivity=self.sensitivity)
            elif self.mode == "bic":
                cps = detect_change_points_bic(self.x, self.sr, sensitivity=self.sensitivity)
            elif self.mode == "voice":
                cps = detect_change_points_voice(self.x, self.sr, sensitivity=self.sensitivity)
            else:  # silence
                cps = detect_change_points_silence(self.x, self.sr, sensitivity=self.sensitivity)

            min_len = int(self.min_seg_s * self.sr)
            points = [0] + sorted(int(c) for c in cps if 0 < c < len(self.x)) + [len(self.x)]
            segs = []
            for i in range(len(points) - 1):
                a, b = points[i], points[i + 1]
                if b - a >= min_len:
                    segs.append((a, b))

            # Фолбэк: если разрывов нет, порежем равными кусками по Min(s)
            if not segs:
                step = min_len
                if step > 0 and len(self.x) > step:
                    cuts = list(range(0, len(self.x), step))
                    if cuts[-1] != len(self.x):
                        cuts.append(len(self.x))
                    segs = [(cuts[i], cuts[i+1]) for i in range(len(cuts)-1) if cuts[i+1]-cuts[i] >= min_len]
                else:
                    segs = [(0, len(self.x))]

            segs = _merge_short(segs, min_len)
            self.done.emit(segs)
        except Exception as e:
            self.error.emit(str(e))


# ---------- Algorithms ----------
def _frame_signal(x: np.ndarray, sr: int, win_ms=25.0, hop_ms=10.0):
    n_win = int(sr * win_ms / 1000.0)
    hop = int(sr * hop_ms / 1000.0)
    n_win = max(64, n_win)
    hop = max(8, hop)
    if len(x) < n_win:
        pad = np.zeros(n_win, dtype=x.dtype)
        pad[: len(x)] = x
        return pad[None, :], n_win, hop
    n_frames = 1 + (len(x) - n_win) // hop
    frames = np.zeros((n_frames, n_win), dtype=x.dtype)
    for i in range(n_frames):
        a = i * hop
        frames[i, :] = x[a : a + n_win]
    return frames, n_win, hop


def detect_change_points_silence(x: np.ndarray, sr: int, sensitivity: float = 1.0) -> List[int]:
    frames, n_win, hop = _frame_signal(x, sr, win_ms=30.0, hop_ms=10.0)
    if frames.shape[0] < 4:
        return []
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    rms_db = 20.0 * np.log10(rms + 1e-12)

    p10 = np.percentile(rms_db, 10)
    p40 = np.percentile(rms_db, 40)
    alpha = np.clip(1.2 - min(1.2, sensitivity), 0.0, 1.2)
    thr = p10 + (p40 - p10) * (0.35 + 0.3 * alpha)

    min_sil = int((0.5 - 0.2 * min(1.0, sensitivity - 0.1)) * sr)  # ~300мс при sens=1
    mask_sil = rms_db < thr
    cps = []
    i = 0
    while i < len(mask_sil):
        if mask_sil[i]:
            j = i
            while j < len(mask_sil) and mask_sil[j]:
                j += 1
            dur = (j - i) * hop
            if dur >= min_sil:
                center = i * hop + dur // 2
                cps.append(int(center))
            i = j
        else:
            i += 1
    min_gap = int(0.8 * sr)
    out = []
    last = None
    for c in sorted(cps):
        if last is None or c - last >= min_gap:
            out.append(c); last = c
    return out


def detect_change_points_energy(x: np.ndarray, sr: int, sensitivity: float = 1.0) -> List[int]:
    frames, n_win, hop = _frame_signal(x, sr)
    ste = np.mean(frames**2, axis=1)
    ste_db = 10.0 * np.log10(1e-12 + ste)
    k = 5
    if len(ste_db) >= 2 * k + 1:
        kernel = np.ones(2 * k + 1) / (2 * k + 1)
        ste_db = np.convolve(ste_db, kernel, mode="same")
    thr = np.percentile(ste_db, 20)
    thr += (np.median(ste_db) - thr) * (1.2 - min(1.2, sensitivity))
    cps = []
    for i in range(2, len(ste_db) - 2):
        if ste_db[i] < thr and ste_db[i] <= ste_db[i - 1] and ste_db[i] <= ste_db[i + 1]:
            cps.append(i * hop)
    return cps


def _mfcc_simple(frames: np.ndarray, sr: int, n_mfcc: int = 13) -> np.ndarray:
    n_fft = frames.shape[1]
    mag = np.abs(np.fft.rfft(frames, axis=1))
    mag = np.maximum(mag, 1e-12)
    n_mel = 20
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    fmin, fmax = 100.0, sr / 2.0
    mel_edges = np.linspace(np.sqrt(fmin), np.sqrt(fmax), n_mel + 2) ** 2
    mel_spec = np.zeros((mag.shape[0], n_mel), dtype=np.float32)
    for m in range(n_mel):
        f0, f1, f2 = mel_edges[m], mel_edges[m + 1], mel_edges[m + 2]
        w = np.zeros_like(freqs)
        w += np.clip((freqs - f0) / (f1 - f0), 0, 1)
        w += np.clip((f2 - freqs) / (f2 - f1), 0, 1)
        w = np.clip(w - 1.0, 0.0, 1.0)
        mel_spec[:, m] = (mag * w).sum(axis=1)
    log_mel = np.log(1e-12 + mel_spec)
    n = log_mel.shape[1]
    k = np.arange(n_mfcc)[:, None]
    n_idx = np.arange(n)[None, :]
    dct_basis = np.cos(np.pi * (n_idx + 0.5) * k / n)
    mfcc = (log_mel @ dct_basis.T) / n
    return mfcc.astype(np.float32)


def detect_change_points_voice(x: np.ndarray, sr: int, sensitivity: float = 1.0) -> List[int]:
    frames, n_win, hop = _frame_signal(x, sr, win_ms=30.0, hop_ms=10.0)
    if frames.shape[0] < 6:
        return []
    mfcc = _mfcc_simple(frames, sr, n_mfcc=13)
    W = min(12, max(2, len(mfcc)//20))
    means = np.array([mfcc[max(0, i - W): i + W + 1].mean(axis=0) for i in range(len(mfcc))])
    a = means[:-1]; b = means[1:]
    dot = np.sum(a * b, axis=1)
    na = np.linalg.norm(a, axis=1) + 1e-9
    nb = np.linalg.norm(b, axis=1) + 1e-9
    cosd = 1.0 - (dot / (na * nb))
    mu = np.mean(cosd); sd = np.std(cosd)
    thr = mu + (0.8 + (1.2 - min(1.2, sensitivity))) * sd
    cps = [ (i+1) * hop for i in range(1, len(cosd)-1) if cosd[i] > thr and cosd[i] >= cosd[i-1] and cosd[i] >= cosd[i+1] ]
    return cps


def detect_change_points_embeddings(x: np.ndarray, sr: int, sensitivity: float = 1.0) -> List[int]:
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav  # type: ignore
    except Exception:
        return detect_change_points_voice(x, sr, sensitivity)

    win = int(1.0 * sr); hop = int(0.5 * sr)
    if len(x) < 2 * win:
        return []
    encoder = VoiceEncoder()
    embs = []
    centers = []
    for a in range(0, len(x) - win + 1, hop):
        b = a + win
        wav_sec = x[a:b]
        try:
            emb = encoder.embed_utterance(wav_sec, rate=sr)
        except Exception:
            emb = encoder.embed_utterance(preprocess_wav(wav_sec, source_sr=sr))
        embs.append(emb)
        centers.append(a + win // 2)
    embs = np.vstack(embs).astype(np.float32)
    a = embs[:-1]; b = embs[1:]
    dot = np.sum(a * b, axis=1)
    na = np.linalg.norm(a, axis=1) + 1e-9
    nb = np.linalg.norm(b, axis=1) + 1e-9
    cosd = 1.0 - (dot / (na * nb))
    mu = np.mean(cosd); sd = np.std(cosd)
    thr = mu + (0.6 + (1.2 - min(1.2, sensitivity))) * sd
    cps = []
    for i in range(1, len(cosd) - 1):
        if cosd[i] > thr and cosd[i] >= cosd[i - 1] and cosd[i] >= cosd[i + 1]:
            cps.append(centers[i])
    return cps


def detect_change_points_bic(x: np.ndarray, sr: int, sensitivity: float = 1.0) -> List[int]:
    frames, n_win, hop = _frame_signal(x, sr, win_ms=30.0, hop_ms=10.0)
    mfcc = _mfcc_simple(frames, sr, n_mfcc=13)
    n = len(mfcc)
    if n < 50:
        return []
    L = 30
    cps = []
    lam = 1.0 * (2.0 - min(1.9, sensitivity))
    for t in range(L, n - L):
        left = mfcc[:t]; right = mfcc[t:]
        SL = np.cov(left.T) + 1e-6 * np.eye(left.shape[1])
        SR = np.cov(right.T) + 1e-6 * np.eye(right.shape[1])
        ALL = mfcc
        SA = np.cov(ALL.T) + 1e-6 * np.eye(ALL.shape[1])
        try:
            logdetL = np.linalg.slogdet(SL)[1]
            logdetR = np.linalg.slogdet(SR)[1]
            logdetA = np.linalg.slogdet(SA)[1]
        except Exception:
            continue
        ll = -0.5 * (t * logdetL + (n - t) * logdetR - n * logdetA)
        penalty = lam * 0.5 * (mfcc.shape[1] + 0.5 * mfcc.shape[1] * (mfcc.shape[1] + 1)) * np.log(n)
        bic = ll - penalty
        if bic > 0:
            cps.append(t * hop)
    min_gap = int(0.8 * sr)
    cps_thin = []
    last = None
    for c in cps:
        if last is None or c - last >= min_gap:
            cps_thin.append(c); last = c
    return cps_thin


def _merge_short(segs: List[Tuple[int,int]], min_len: int) -> List[Tuple[int,int]]:
    if not segs:
        return segs
    out = [segs[0]]
    for s in segs[1:]:
        a0, b0 = out[-1]; a1, b1 = s
        if b0 - a0 < min_len:
            out[-1] = (a0, b1)
        else:
            out.append(s)
    if out and (out[-1][1] - out[-1][0] < min_len) and len(out) >= 2:
        out[-2] = (out[-2][0], out[-1][1])
        out = out[:-1]
    return out