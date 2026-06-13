"""Locate ffmpeg binaries shipped alongside the application."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional


def find_ffmpeg(custom_dir: Optional[Path] = None) -> Optional[Path]:
    candidates = []
    if custom_dir is not None:
        candidates.append(custom_dir / "ffmpeg.exe")
        candidates.append(custom_dir / "ffmpeg")
    else:
        third_party_dir = Path(__file__).resolve().parent
        candidates.append(third_party_dir / "ffmpeg.exe")
        candidates.append(third_party_dir / "ffmpeg")
        env = os.environ.get("FFMPEG_PATH")
        if env:
            candidates.append(Path(env))
        path_binary = shutil.which("ffmpeg")
        if path_binary:
            candidates.append(Path(path_binary))
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


__all__ = ["find_ffmpeg"]
