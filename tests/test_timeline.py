from __future__ import annotations

from app.audio.engine import Recorder, preroll_sequence
from app.timeline.model import Timeline


def test_record_and_blade(tmp_path):
    timeline = Timeline()
    track = timeline.add_track("Voice", "#4caf50")
    timeline.arm_track(track.id)
    recorder = Recorder(timeline)
    result = recorder.record(track.id, duration=1.0)
    assert len(track.clips) == 1
    clip = track.clips[0]
    assert clip.active_take() is not None
    split_clip = timeline.blade(clip.id, position=0.5)
    assert split_clip.track_id == track.id
    assert len(track.clips) == 2


def test_preroll_sequence_contains_go():
    cues = list(preroll_sequence())
    names = [cue.name for cue in cues]
    assert names.count("go") == 1
    assert any(name.startswith("beep") for name in names)
