from __future__ import annotations

import json
from pathlib import Path

from app.settings.storage import SettingsStorage


def test_hotkey_import_export(tmp_path):
    storage = SettingsStorage(tmp_path)
    storage.set_hotkey("play_pause", "Enter")
    export_path = tmp_path / "hotkeys.json"
    storage.export_hotkeys(export_path)
    payload = json.loads(export_path.read_text())
    assert payload["play_pause"] == "Enter"

    new_storage = SettingsStorage(tmp_path / "alt")
    new_storage.import_hotkeys(export_path)
    assert new_storage.hotkey_bindings()["play_pause"] == "Enter"


def test_settings_persistence(tmp_path):
    storage = SettingsStorage(tmp_path)
    storage.set_option("audio", "mp3_bitrate", 256)
    storage2 = SettingsStorage(tmp_path)
    assert storage2.get_option("audio", "mp3_bitrate") == 256
