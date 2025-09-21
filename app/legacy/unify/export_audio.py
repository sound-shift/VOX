"""Minimal wrapper referencing the legacy exporter implementation."""
from __future__ import annotations

from .ui_main import ExportDialog  # type: ignore  # noqa: F401

__all__ = ["ExportDialog"]
