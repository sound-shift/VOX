from __future__ import annotations

from pathlib import Path

import math

from app.project.database import ProjectDatabase
from app.timeline.model import Timeline


def test_project_save_and_load(tmp_path):
    project_path = tmp_path / "test.voxproj"
    db = ProjectDatabase(project_path)
    db.initialize()

    timeline = Timeline()
    track = timeline.add_track("Track", "#4caf50")
    clip = timeline.add_clip(track.id, 0.0, 1.0)
    data = [math.sin(2 * math.pi * 220.0 * (i / 48000)) * 0.1 for i in range(48000)]
    timeline.add_take(clip, data=data, start=0.0, end=1.0, active=True)
    marker = timeline.add_marker(0.5, "Test")

    db.save_timeline(timeline, tmp_path / "audio")
    loaded = db.load_timeline()

    assert len(loaded.tracks) == 1
    loaded_track = next(iter(loaded.tracks.values()))
    assert len(loaded_track.clips) == 1
    assert loaded_track.clips[0].active_take() is not None
    assert marker.id in loaded.markers
