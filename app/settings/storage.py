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


@dataclass
class SettingsStorage:
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
