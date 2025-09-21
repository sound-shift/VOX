"""Compatibility module exposing loudness helpers from the legacy core."""
from __future__ import annotations

from .core import loudnorm  # noqa: F401

__all__ = ["loudnorm"]
