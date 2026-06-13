"""Timeline data model for VOX."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Marker:
    id: int
    position: float
    name: str


@dataclass
class Take:
    id: int
    clip_id: int
    index: int
    data: List[float]
    start: float
    end: float
    active: bool = False

    def duration(self) -> float:
        return float(self.end - self.start)


@dataclass
class Clip:
    id: int
    track_id: int
    start: float
    end: float
    takes: List[Take] = field(default_factory=list)

    def duration(self) -> float:
        return float(self.end - self.start)

    def active_take(self) -> Optional[Take]:
        for take in self.takes:
            if take.active:
                return take
        return None

    def set_active_take(self, take_id: int) -> None:
        for take in self.takes:
            take.active = take.id == take_id


@dataclass
class Track:
    id: int
    name: str
    color: str
    clips: List[Clip] = field(default_factory=list)
    armed: bool = False
    monitor_processed: bool = False


class Timeline:
    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate
        self.tracks: Dict[int, Track] = {}
        self.markers: Dict[int, Marker] = {}
        self._next_track_id = 1
        self._next_clip_id = 1
        self._next_take_id = 1
        self._next_marker_id = 1

    # tracks
    def add_track(self, name: str, color: str) -> Track:
        track = Track(id=self._next_track_id, name=name, color=color)
        self.tracks[track.id] = track
        self._next_track_id += 1
        return track

    def arm_track(self, track_id: int, armed: bool = True) -> None:
        self.tracks[track_id].armed = armed

    def get_track(self, track_id: int) -> Track:
        return self.tracks[track_id]

    # clips and takes
    def add_clip(self, track_id: int, start: float, end: float) -> Clip:
        clip = Clip(id=self._next_clip_id, track_id=track_id, start=start, end=end)
        self._next_clip_id += 1
        self.tracks[track_id].clips.append(clip)
        return clip

    def add_take(self, clip: Clip, data: List[float], start: float, end: float, active: bool = True) -> Take:
        take = Take(
            id=self._next_take_id,
            clip_id=clip.id,
            index=len(clip.takes) + 1,
            data=list(data),
            start=start,
            end=end,
            active=active,
        )
        self._next_take_id += 1
        clip.takes.append(take)
        if active:
            clip.set_active_take(take.id)
        return take

    def blade(self, clip_id: int, position: float) -> Clip:
        for track in self.tracks.values():
            for clip in track.clips:
                if clip.id == clip_id:
                    clip_start = clip.start
                    clip_end = clip.end
                    if not (clip_start < position < clip_end):
                        raise ValueError("Split position must be within clip bounds")
                    clip_duration = clip_end - clip_start
                    new_clip = Clip(id=self._next_clip_id, track_id=clip.track_id, start=position, end=clip_end)
                    self._next_clip_id += 1
                    clip.end = position
                    new_takes: List[Take] = []
                    for take in clip.takes:
                        total_samples = len(take.data)
                        if clip_duration <= 0 or total_samples == 0:
                            split_index = 0
                        else:
                            split_ratio = (position - clip_start) / clip_duration
                            split_index = int(round(total_samples * split_ratio))
                        left_data = take.data[:split_index]
                        right_data = take.data[split_index:]
                        left = Take(
                            id=take.id,
                            clip_id=clip.id,
                            index=take.index,
                            data=list(left_data),
                            start=take.start,
                            end=min(position, take.end),
                            active=take.active,
                        )
                        right = Take(
                            id=self._next_take_id,
                            clip_id=new_clip.id,
                            index=take.index,
                            data=list(right_data),
                            start=max(position, take.start),
                            end=take.end,
                            active=take.active,
                        )
                        self._next_take_id += 1
                        new_takes.append(left)
                        new_clip.takes.append(right)
                    clip.takes = new_takes
                    track.clips.append(new_clip)
                    return new_clip
        raise KeyError(f"Clip {clip_id} not found")

    # markers
    def add_marker(self, position: float, name: str) -> Marker:
        marker = Marker(id=self._next_marker_id, position=position, name=name)
        self.markers[marker.id] = marker
        self._next_marker_id += 1
        return marker

    def move_marker(self, marker_id: int, new_position: float) -> None:
        self.markers[marker_id].position = new_position

    def remove_marker(self, marker_id: int) -> None:
        self.markers.pop(marker_id, None)

    def cycle_active_take(self, clip_id: int, direction: int = 1) -> Optional[int]:
        for track in self.tracks.values():
            for clip in track.clips:
                if clip.id != clip_id or not clip.takes:
                    continue
                take_ids = [take.id for take in clip.takes]
                active = clip.active_take()
                if active is None:
                    clip.set_active_take(take_ids[0])
                    return take_ids[0]
                idx = take_ids.index(active.id)
                next_id = take_ids[(idx + direction) % len(take_ids)]
                clip.set_active_take(next_id)
                return next_id
        return None

    def set_active_take(self, clip_id: int, take_id: int) -> bool:
        for track in self.tracks.values():
            for clip in track.clips:
                if clip.id == clip_id:
                    if any(t.id == take_id for t in clip.takes):
                        clip.set_active_take(take_id)
                        return True
                    return False
        return False

    def find_clip(self, clip_id: int) -> Optional[Clip]:
        for track in self.tracks.values():
            for clip in track.clips:
                if clip.id == clip_id:
                    return clip
        return None


__all__ = ["Timeline", "Track", "Clip", "Take", "Marker"]
