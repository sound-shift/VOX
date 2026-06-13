"""Persistent storage for user preferences and hotkeys."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, MutableMapping

DEFAULT_SETTINGS = {
    "audio": {"mp3_bitrate": 192},
    "autosave": {"interval_sec": 300, "slots": 5},
    "processing": {
        "reference_file": None,
        "noise_profile": None,
    },
    "ui": {"geometry": None, "tour_completed": False},
}

DEFAULT_HOTKEYS = {
    "play_pause": "Space",
    "record_take": "*",
    "arm_track": "R",
    "record_armed": "Shift+R",
    "blade": "B",
    "marker": "M",
    "toggle_takelanes": "L",
    "zoom_in": "Z",
    "zoom_out": "X",
    "save": "Ctrl+S",
    "save_as": "Shift+S",
    "open": "Ctrl+O",
    "new": "Ctrl+N",
    "export": "Ctrl+E",
    "import": "Ctrl+I",
    "bypass_processing": "Ctrl+B",
    "monitor_processed": "Ctrl+T",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Shift+Z",
    "loop_in": "[",
    "loop_out": "]",
    "toggle_loop": "\\",
    "punch_record": "P",
}


@dataclass
class SettingsStorage:
    root: Path
    data: Dict[str, MutableMapping[str, object]] = field(
        default_factory=lambda: json.loads(json.dumps(DEFAULT_SETTINGS))
    )
    hotkeys: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._settings_file = self.root / "settings.json"
        self._hotkeys_file = self.root / "hotkeys.json"
        self.load()

    def set_option(self, section: str, key: str, value) -> None:
        self.data.setdefault(section, {})[key] = value
        self.save()

    def get_option(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    def set_hotkey(self, action: str, binding: str) -> None:
        self.hotkeys[action] = binding
        self.save_hotkeys()

    def reset_hotkey(self, action: str) -> None:
        if action in DEFAULT_HOTKEYS:
            self.hotkeys[action] = DEFAULT_HOTKEYS[action]
        else:
            self.hotkeys.pop(action, None)
        self.save_hotkeys()

    def import_hotkeys(self, path: Path) -> None:
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Invalid hotkeys file")
        self.hotkeys.update({k: str(v) for k, v in payload.items()})
        self.save_hotkeys()

    def export_hotkeys(self, path: Path) -> None:
        path.write_text(json.dumps(self.hotkeys, indent=2, ensure_ascii=False))

    def hotkey_bindings(self) -> Dict[str, str]:
        return dict(self.hotkeys)

    def load(self) -> None:
        if self._settings_file.exists():
            payload = json.loads(self._settings_file.read_text())
            self.data.update(payload)
        if self._hotkeys_file.exists():
            payload = json.loads(self._hotkeys_file.read_text())
            if isinstance(payload, dict):
                self.hotkeys.update({k: str(v) for k, v in payload.items()})

    def save(self) -> None:
        self._settings_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    def save_hotkeys(self) -> None:
        self._hotkeys_file.write_text(json.dumps(self.hotkeys, indent=2, ensure_ascii=False))


__all__ = ["SettingsStorage", "DEFAULT_SETTINGS", "DEFAULT_HOTKEYS"]
