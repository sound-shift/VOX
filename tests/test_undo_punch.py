from __future__ import annotations

from app.audio.engine import Recorder
from app.timeline.model import Timeline
from app.timeline.undo import UndoStack


def test_undo_redo_after_blade():
    timeline = Timeline()
    track = timeline.add_track("Voice", "#4caf50")
    timeline.arm_track(track.id)
    recorder = Recorder(timeline)
    recorder.record(track.id, duration=1.0, prefer_live=False)
    clip = track.clips[0]
    stack = UndoStack()
    stack.reset(timeline)
    stack.push(timeline)
    timeline.blade(clip.id, 0.5)
    assert len(track.clips) == 2
    assert stack.undo(timeline)
    restored = timeline.get_track(track.id)
    assert len(restored.clips) == 1
    assert stack.redo(timeline)
    assert len(timeline.get_track(track.id).clips) == 2


def test_punch_record_splices_take():
    timeline = Timeline()
    track = timeline.add_track("Dialog", "#4caf50")
    timeline.arm_track(track.id)
    recorder = Recorder(timeline)
    recorder.record(track.id, duration=2.0, prefer_live=False)
    clip = track.clips[0]
    original_take_count = len(clip.takes)
    result = recorder.punch_record(track.id, 0.5, 1.0, prefer_live=False)
    assert result.clip.id == clip.id
    assert len(clip.takes) == original_take_count + 1
    assert clip.active_take() is not None
    assert len(clip.active_take().data) == len(clip.takes[0].data)
