"""Compatibility wrapper exposing the original Unify dark theme helpers."""
from __future__ import annotations

from .widgets import apply_dark_theme, make_tile  # noqa: F401

__all__ = ["apply_dark_theme", "make_tile"]
