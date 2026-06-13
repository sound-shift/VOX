"""Voice presets and EQ curves used by VOX."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class VoicePreset:
    name: str
    tilt_db_per_oct: float
    presence_gain_db: float
    presence_range: tuple[float, float]
    low_guard_hz: float
    deesser_range: tuple[float, float] | None = None
    low_shelf_gain_db: float = 0.0


PRESETS: Dict[str, VoicePreset] = {
    "male_low": VoicePreset(
        name="Male Low",
        tilt_db_per_oct=-1.5,
        presence_gain_db=2.5,
        presence_range=(3200.0, 4200.0),
        low_guard_hz=70.0,
    ),
    "male_high": VoicePreset(
        name="Male High",
        tilt_db_per_oct=-1.0,
        presence_gain_db=3.0,
        presence_range=(3500.0, 5000.0),
        low_guard_hz=70.0,
    ),
    "female_low": VoicePreset(
        name="Female Low",
        tilt_db_per_oct=-0.8,
        presence_gain_db=3.5,
        presence_range=(3000.0, 5500.0),
        low_guard_hz=80.0,
        deesser_range=(6000.0, 8000.0),
    ),
    "female_high": VoicePreset(
        name="Female High",
        tilt_db_per_oct=-0.5,
        presence_gain_db=4.0,
        presence_range=(3000.0, 6000.0),
        low_guard_hz=90.0,
        low_shelf_gain_db=1.5,
    ),
    "adr_dialog": VoicePreset(
        name="ADR / Dialog",
        tilt_db_per_oct=-0.6,
        presence_gain_db=3.2,
        presence_range=(2800.0, 4500.0),
        low_guard_hz=100.0,
        deesser_range=(5500.0, 9000.0),
        low_shelf_gain_db=0.5,
    ),
}


def get_preset(key: str) -> VoicePreset:
    try:
        return PRESETS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown preset '{key}'. Available: {', '.join(sorted(PRESETS))}") from exc


__all__ = ["VoicePreset", "get_preset", "PRESETS"]
