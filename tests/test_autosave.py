from __future__ import annotations

from pathlib import Path

from app.project.database import AutosaveManager


def test_autosave_ring(tmp_path):
    project = tmp_path / "project.voxproj"
    project.write_text("dummy")
    manager = AutosaveManager(project, slots=5)
    paths = [manager.autosave(project) for _ in range(6)]
    assert len(list(manager.available())) <= 5
