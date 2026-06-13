"""Snapshot-based undo/redo for the timeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.timeline.model import Timeline


def _snapshot_timeline(timeline: Timeline) -> Dict[str, Any]:
    tracks: List[Dict[str, Any]] = []
    for track in timeline.tracks.values():
        clips: List[Dict[str, Any]] = []
        for clip in track.clips:
            takes = [
                {
                    "id": take.id,
                    "clip_id": take.clip_id,
                    "index": take.index,
                    "data": list(take.data),
                    "start": take.start,
                    "end": take.end,
                    "active": take.active,
                }
                for take in clip.takes
            ]
            clips.append(
                {
                    "id": clip.id,
                    "track_id": clip.track_id,
                    "start": clip.start,
                    "end": clip.end,
                    "takes": takes,
                }
            )
        tracks.append(
            {
                "id": track.id,
                "name": track.name,
                "color": track.color,
                "armed": track.armed,
                "monitor_processed": track.monitor_processed,
                "clips": clips,
            }
        )
    markers = [
        {"id": m.id, "position": m.position, "name": m.name}
        for m in timeline.markers.values()
    ]
    return {
        "sample_rate": timeline.sample_rate,
        "tracks": tracks,
        "markers": markers,
        "next_track_id": timeline._next_track_id,
        "next_clip_id": timeline._next_clip_id,
        "next_take_id": timeline._next_take_id,
        "next_marker_id": timeline._next_marker_id,
    }


def _restore_timeline(timeline: Timeline, snap: Dict[str, Any]) -> None:
    from app.timeline.model import Clip, Marker, Take, Track

    timeline.sample_rate = int(snap["sample_rate"])
    timeline.tracks.clear()
    timeline.markers.clear()
    for td in snap["tracks"]:
        track = Track(
            id=td["id"],
            name=td["name"],
            color=td["color"],
            armed=td["armed"],
            monitor_processed=td["monitor_processed"],
        )
        for cd in td["clips"]:
            clip = Clip(id=cd["id"], track_id=cd["track_id"], start=cd["start"], end=cd["end"])
            for tk in cd["takes"]:
                clip.takes.append(
                    Take(
                        id=tk["id"],
                        clip_id=tk["clip_id"],
                        index=tk["index"],
                        data=list(tk["data"]),
                        start=tk["start"],
                        end=tk["end"],
                        active=tk["active"],
                    )
                )
            track.clips.append(clip)
        timeline.tracks[track.id] = track
    for md in snap["markers"]:
        timeline.markers[md["id"]] = Marker(id=md["id"], position=md["position"], name=md["name"])
    timeline._next_track_id = snap["next_track_id"]
    timeline._next_clip_id = snap["next_clip_id"]
    timeline._next_take_id = snap["next_take_id"]
    timeline._next_marker_id = snap["next_marker_id"]


@dataclass
class UndoStack:
    max_depth: int = 40
    _undo: List[Dict[str, Any]] = field(default_factory=list)
    _redo: List[Dict[str, Any]] = field(default_factory=list)

    def can_undo(self) -> bool:
        return len(self._undo) > 1

    def can_redo(self) -> bool:
        return bool(self._redo)

    def push(self, timeline: Timeline) -> None:
        """Save timeline state before a mutating action."""
        self._undo.append(_snapshot_timeline(timeline))
        if len(self._undo) > self.max_depth:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, timeline: Timeline) -> bool:
        if len(self._undo) <= 1:
            return False
        self._redo.append(_snapshot_timeline(timeline))
        self._undo.pop()
        _restore_timeline(timeline, self._undo[-1])
        return True

    def redo(self, timeline: Timeline) -> bool:
        if not self._redo:
            return False
        self._undo.append(_snapshot_timeline(timeline))
        snap = self._redo.pop()
        _restore_timeline(timeline, snap)
        return True

    def reset(self, timeline: Timeline) -> None:
        self._undo = [_snapshot_timeline(timeline)]
        self._redo.clear()


__all__ = ["UndoStack", "_snapshot_timeline", "_restore_timeline"]
