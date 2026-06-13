"""Magic processing — delegates to the Unify pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.dsp.pipeline import ProcessingOptions, ProcessResult, process_take


def process_magic(
    signal: List[float],
    sr: int,
    preset_key: str,
    reference: Optional[List[float]] = None,
    *,
    reference_path: Optional[Path] = None,
    match_weight: float = 1.0,
    isolation_amount: float = 0.0,
    dereverb_amount: float = 0.35,
    denoise_reduction_db: float = 12.0,
    gate_enable: bool = False,
    bypass: bool = False,
) -> ProcessResult:
    ref_path = reference_path
    if ref_path is None and reference:
        # Legacy inline reference — write temp for match EQ
        from app.audio.engine import write_wav_mono

        tmp = Path(".vox_takes") / "_ref_tmp.wav"
        tmp.parent.mkdir(exist_ok=True)
        write_wav_mono(tmp, reference, sr)
        ref_path = tmp

    opts = ProcessingOptions(
        preset_key=preset_key,
        reference_path=ref_path,
        match_weight=match_weight,
        isolation_amount=isolation_amount,
        dereverb_amount=dereverb_amount,
        denoise_reduction_db=denoise_reduction_db,
        gate_enable=gate_enable,
        bypass=bypass,
    )
    return process_take(signal, sr, opts)


# Backward-compatible alias
MagicResult = ProcessResult

__all__ = ["MagicResult", "ProcessResult", "process_magic", "process_take", "ProcessingOptions"]
