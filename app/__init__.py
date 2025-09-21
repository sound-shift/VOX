"""Application package for the VOX desktop client."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure that the repository root (which hosts the legacy modules such as
# ``AudioUnify`` and ``Core``) is importable when ``python -m app`` is used.
_PACKAGE_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_ROOT.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

__all__ = ["_PROJECT_ROOT"]
