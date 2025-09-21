codex/fix-modulenotfounderror-for-app
"""Persistent storage helpers for user settings.

The original project ships the DSP/GUI implementation in monolithic modules
(`AudioUnify.py`, `Core.py`, …).  To make the application shippable as a
package we provide a light-weight JSON based storage that can persist user
preferences (window geometry, last used folders, …).
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, MutableMapping

__all__ = ["SettingsStorage", "load_settings", "default_storage_path"]

_SENTINEL = object()
=======
"""Persistent storage for user preferences and hotkeys."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, MutableMapping

DEFAULT_SETTINGS = {
    "audio": {"mp3_bitrate": 192},
    "autosave": {"interval_sec": 300, "slots": 5},
    "processing": {"reference_file": None},
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
}
main


@dataclass
class SettingsStorage:
codex/fix-modulenotfounderror-for-app
    """Serialize settings to a JSON file on disk.

    Parameters
    ----------
    path:
        Optional path where the JSON file should be stored.  When omitted a
        platform dependent application directory is used.
    auto_load:
        When set to ``True`` the class will immediately call :meth:`load` in the
        constructor.  This is a convenience for one-liners such as
        ``storage = SettingsStorage(auto_load=True)``.
    """

    path: Path | None = None
    auto_load: bool = False
    _data: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = default_storage_path()
        else:
            self.path = Path(self.path)
        if self.auto_load:
            self.load()

    # ------------------------------------------------------------------
    # Mapping style API
    # ------------------------------------------------------------------
    def load(self) -> Dict[str, Any]:
        """Load the JSON file if it exists.

        Any JSON decoding error results in an empty configuration; the corrupted
        file is left untouched so that the user can manually recover it.
        """

        try:
            with self.path.open("r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except FileNotFoundError:
            self._data = {}
        except json.JSONDecodeError:
            # Keep a backup of the broken file for potential debugging.
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            try:
                if self.path.exists():
                    self.path.replace(backup_path)
            except OSError:
                # If we cannot backup the file we simply reset the data.
                pass
            self._data = {}
        return self._data

    def save(self) -> None:
        """Persist the current data to disk."""

        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, sort_keys=True)

    def get(self, key: str, default: Any | None = None) -> Any:
        """Retrieve a value using dotted notation."""

        data: Any = self._data
        for part in key.split("."):
            if not isinstance(data, dict) or part not in data:
                return default
            data = data[part]
        return data

    def set(self, key: str, value: Any) -> None:
        """Assign a value using dotted notation."""

        parts = key.split(".")
        data: Dict[str, Any] = self._data
        for part in parts[:-1]:
            next_item = data.get(part)
            if not isinstance(next_item, dict):
                next_item = {}
                data[part] = next_item
            data = next_item
        data[parts[-1]] = value

    def update(self, values: MutableMapping[str, Any]) -> None:
        """Merge ``values`` into the storage using a deep update."""

        def _merge(target: MutableMapping[str, Any], source: MutableMapping[str, Any]) -> None:
            for key, value in source.items():
                if isinstance(value, MutableMapping) and isinstance(target.get(key), MutableMapping):
                    _merge(target[key], value)  # type: ignore[index]
                else:
                    target[key] = deepcopy(value)

        _merge(self._data, values)

    def as_dict(self) -> Dict[str, Any]:
        """Return a deep copy of the stored settings."""

        return deepcopy(self._data)

    def reset(self) -> None:
        """Remove all stored settings from memory."""

        self._data.clear()

    # Python mapping sugar -------------------------------------------------
    def __contains__(self, key: object) -> bool:  # pragma: no cover - convenience
        if not isinstance(key, str):
            return False
        return self.get(key, _SENTINEL) is not _SENTINEL

    def __getitem__(self, key: str) -> Any:  # pragma: no cover - convenience
        value = self.get(key, _SENTINEL)
        if value is _SENTINEL:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:  # pragma: no cover
        self.set(key, value)

    def __repr__(self) -> str:  # pragma: no cover - helpful during debugging
        return f"SettingsStorage(path={self.path!s}, data={self._data!r})"


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def default_storage_path(filename: str = "settings.json") -> Path:
    """Compute the default storage path for the application."""

    env = os.environ.get("VOX_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve() / filename

    # Use a hidden folder in the user's home directory by default.
    home = Path.home()
    return (home / ".voiceoverx").resolve() / filename


def load_settings(path: Path | None = None) -> SettingsStorage:
    """Convenience wrapper returning a loaded :class:`SettingsStorage`."""

    storage = SettingsStorage(path=path, auto_load=True)
    return storage
=======
    root: Path
    data: Dict[str, MutableMapping[str, object]] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_SETTINGS)))
    hotkeys: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._settings_file = self.root / "settings.json"
        self._hotkeys_file = self.root / "hotkeys.json"
        self.load()

    # general options
    def set_option(self, section: str, key: str, value) -> None:
        self.data.setdefault(section, {})[key] = value
        self.save()

    def get_option(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    # hotkeys
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

    # persistence
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
main
