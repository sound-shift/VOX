"""Video preview quality placeholders."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class PreviewQuality(str, Enum):
    FULL = "full"
    HALF = "half"
    QUARTER = "quarter"
    EIGHTH = "draft"


@dataclass
class QualityProfile:
    name: str
    downscale_factor: float
    drop_frames: bool


QUALITY_PROFILES: Dict[PreviewQuality, QualityProfile] = {
    PreviewQuality.FULL: QualityProfile("Full", 1.0, False),
    PreviewQuality.HALF: QualityProfile("Half", 2.0, False),
    PreviewQuality.QUARTER: QualityProfile("Quarter", 4.0, False),
    PreviewQuality.EIGHTH: QualityProfile("Draft", 8.0, True),
}


__all__ = ["PreviewQuality", "QualityProfile", "QUALITY_PROFILES"]
