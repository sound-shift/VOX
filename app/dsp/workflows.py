"""Per-workflow defaults applied at session start."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class WorkflowConfig:
    preset_key: str
    record_duration_sec: float
    match_weight: float
    isolation_amount: float
    dereverb_amount: float
    denoise_db: float
    denoise_floor_db: float
    denoise_sensitivity: float
    gate_enable: bool
    tilt_db_per_oct: Optional[float] = None


WORKFLOWS: Dict[str, WorkflowConfig] = {
    "podcast": WorkflowConfig(
        preset_key="male_low",
        record_duration_sec=5.0,
        match_weight=1.0,
        isolation_amount=0.0,
        dereverb_amount=0.35,
        denoise_db=12.0,
        denoise_floor_db=-36.0,
        denoise_sensitivity=0.5,
        gate_enable=False,
    ),
    "audiobook": WorkflowConfig(
        preset_key="male_low",
        record_duration_sec=8.0,
        match_weight=0.9,
        isolation_amount=0.0,
        dereverb_amount=0.4,
        denoise_db=14.0,
        denoise_floor_db=-38.0,
        denoise_sensitivity=0.55,
        gate_enable=True,
    ),
    "adr": WorkflowConfig(
        preset_key="adr_dialog",
        record_duration_sec=12.0,
        match_weight=0.85,
        isolation_amount=0.15,
        dereverb_amount=0.5,
        denoise_db=16.0,
        denoise_floor_db=-42.0,
        denoise_sensitivity=0.65,
        gate_enable=True,
        tilt_db_per_oct=-0.6,
    ),
}


def get_workflow(mode: str) -> WorkflowConfig:
    return WORKFLOWS.get(mode, WORKFLOWS["podcast"])


__all__ = ["WorkflowConfig", "WORKFLOWS", "get_workflow"]
