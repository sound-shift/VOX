"""SQLite-backed project storage for .voxproj files."""
from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from app.timeline.model import Clip, Marker, Take, Timeline, Track

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        color TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS clips (
        id INTEGER PRIMARY KEY,
        track_id INTEGER NOT NULL,
        start REAL NOT NULL,
        end REAL NOT NULL,
        FOREIGN KEY(track_id) REFERENCES tracks(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS takes (
        id INTEGER PRIMARY KEY,
        clip_id INTEGER NOT NULL,
        idx INTEGER NOT NULL,
        start REAL NOT NULL,
        end REAL NOT NULL,
        active INTEGER NOT NULL,
        data_json TEXT NOT NULL,
        FOREIGN KEY(clip_id) REFERENCES clips(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS markers (
        id INTEGER PRIMARY KEY,
        position REAL NOT NULL,
        name TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY,
        path TEXT NOT NULL,
        role TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS fx_chains (
        id INTEGER PRIMARY KEY,
        track_id INTEGER,
        data TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS versions (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
]


@dataclass
class ProjectMeta:
    path: Path
    autosave_slots: int = 5
    autosave_interval_sec: int = 300


class ProjectDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self.connection is None:
            self.connection = sqlite3.connect(self.path)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def initialize(self) -> None:
        con = self.connect()
        for stmt in SCHEMA:
            con.execute(stmt)
        con.commit()

    # timeline persistence
    def save_timeline(self, timeline: Timeline, audio_dir: Path) -> None:
        con = self.connect()
        cur = con.cursor()
        audio_dir.mkdir(exist_ok=True)
        cur.execute("DELETE FROM tracks")
        cur.execute("DELETE FROM clips")
        cur.execute("DELETE FROM takes")
        cur.execute("DELETE FROM markers")
        for track in timeline.tracks.values():
            cur.execute("INSERT INTO tracks(id, name, color) VALUES (?, ?, ?)", (track.id, track.name, track.color))
            for clip in track.clips:
                cur.execute(
                    "INSERT INTO clips(id, track_id, start, end) VALUES (?, ?, ?, ?)",
                    (clip.id, track.id, clip.start, clip.end),
                )
                for take in clip.takes:
                    cur.execute(
                        "INSERT INTO takes(id, clip_id, idx, start, end, active, data_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            take.id,
                            clip.id,
                            take.index,
                            take.start,
                            take.end,
                            1 if take.active else 0,
                            json.dumps(take.data),
                        ),
                    )
        for marker in timeline.markers.values():
            cur.execute("INSERT INTO markers(id, position, name) VALUES (?, ?, ?)", (marker.id, marker.position, marker.name))
        con.commit()

    def load_timeline(self) -> Timeline:
        timeline = Timeline()
        con = self.connect()
        cur = con.cursor()
        for row in cur.execute("SELECT id, name, color FROM tracks ORDER BY id"):
            track = Track(id=row["id"], name=row["name"], color=row["color"])
            timeline.tracks[track.id] = track
        timeline._next_track_id = max(timeline.tracks.keys(), default=0) + 1
        for row in cur.execute("SELECT id, track_id, start, end FROM clips ORDER BY id"):
            clip = Clip(id=row["id"], track_id=row["track_id"], start=row["start"], end=row["end"])
            timeline.tracks[clip.track_id].clips.append(clip)
            timeline._next_clip_id = max(timeline._next_clip_id, clip.id + 1)
        takes = list(cur.execute("SELECT id, clip_id, idx, start, end, active, data_json FROM takes ORDER BY id"))
        for row in takes:
            data = json.loads(row["data_json"])
            take = Take(
                id=row["id"],
                clip_id=row["clip_id"],
                index=row["idx"],
                data=data,
                start=row["start"],
                end=row["end"],
                active=bool(row["active"]),
            )
            timeline._next_take_id = max(timeline._next_take_id, take.id + 1)
            clip = next(c for t in timeline.tracks.values() for c in t.clips if c.id == take.clip_id)
            clip.takes.append(take)
        for row in cur.execute("SELECT id, position, name FROM markers ORDER BY id"):
            marker = Marker(id=row["id"], position=row["position"], name=row["name"])
            timeline.markers[marker.id] = marker
            timeline._next_marker_id = max(timeline._next_marker_id, marker.id + 1)
        return timeline

    # settings persistence
    def save_setting(self, key: str, value: dict) -> None:
        con = self.connect()
        con.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        con.commit()

    def load_setting(self, key: str, default: Optional[dict] = None) -> dict:
        con = self.connect()
        cur = con.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        if row is None:
            return {} if default is None else default
        return json.loads(row[0])


class AutosaveManager:
    def __init__(self, project_path: Path, slots: int = 5) -> None:
        self.project_path = project_path
        self.slots = max(5, slots)
        self.autosave_dir = project_path.parent / "autosaves"
        self.autosave_dir.mkdir(exist_ok=True)

    def autosave(self, source: Path, index: Optional[int] = None) -> Path:
        if index is None:
            index = self._next_index()
        target = self.autosave_dir / f"VOX-Autosave-{index}.voxproj"
        shutil.copy2(source, target)
        return target

    def _next_index(self) -> int:
        existing = sorted(self.autosave_dir.glob("VOX-Autosave-*.voxproj"))
        if not existing:
            return 1
        if len(existing) >= self.slots:
            for path in existing[:-self.slots + 1]:
                path.unlink(missing_ok=True)
        last = existing[-1]
        try:
            idx = int(last.stem.split("-")[-1]) + 1
        except ValueError:
            idx = len(existing) + 1
        if idx > self.slots:
            idx = 1
        return idx

    def available(self) -> Iterable[Path]:
        return sorted(self.autosave_dir.glob("VOX-Autosave-*.voxproj"))


__all__ = ["ProjectDatabase", "ProjectMeta", "AutosaveManager"]
