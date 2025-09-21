codex/fix-modulenotfounderror-for-app
"""Application entry-point for the VOX desktop client."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.settings import SettingsStorage

# ``AudioUnify`` and the supporting modules live at the repository root.  When
# ``python -m app`` is executed we need to ensure those modules are importable.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from AudioUnify import APP_VERSION, MainWindow  # noqa: E402
from widgets import apply_dark_theme  # noqa: E402

WINDOW_GEOMETRY_KEY = "ui.window_geometry"
WINDOW_STATE_KEY = "ui.window_state"


def _restore_window_state(window: QtWidgets.QMainWindow, storage: SettingsStorage) -> None:
    """Restore the geometry/state of ``window`` if we have previously stored it."""

    geometry_hex: Optional[str] = storage.get(WINDOW_GEOMETRY_KEY)
    if isinstance(geometry_hex, str) and geometry_hex:
        try:
            geometry = QtCore.QByteArray.fromHex(geometry_hex.encode("ascii"))
            if not geometry.isEmpty():
                window.restoreGeometry(geometry)
        except (TypeError, ValueError):
            pass

    state_hex: Optional[str] = storage.get(WINDOW_STATE_KEY)
    if isinstance(state_hex, str) and state_hex:
        try:
            state = QtCore.QByteArray.fromHex(state_hex.encode("ascii"))
            if not state.isEmpty():
                window.restoreState(state)
        except (TypeError, ValueError):
            pass


def _persist_window_state(window: QtWidgets.QMainWindow, storage: SettingsStorage) -> None:
    """Save the current geometry/state so it can be restored next launch."""

    geometry = window.saveGeometry().toHex()
    storage.set(WINDOW_GEOMETRY_KEY, bytes(geometry).decode("ascii"))

    state = window.saveState().toHex()
    storage.set(WINDOW_STATE_KEY, bytes(state).decode("ascii"))


def main() -> int:
    """Launch the Qt application."""

    storage = SettingsStorage(auto_load=True)

    app = QtWidgets.QApplication(sys.argv)
    try:
        base_size = int(os.environ.get("VOX_BASE_FONT", "9"))
        apply_dark_theme(app, base_font_point_size=base_size)
    except Exception:
        # Theme application is purely cosmetic; we should not abort if it fails.
        pass

    window = MainWindow()
    window.setWindowTitle(f"Unify Audio – {APP_VERSION}")

    _restore_window_state(window, storage)
    window.show()

    exit_code = app.exec()

    _persist_window_state(window, storage)
    storage.save()

    return int(exit_code)
=======
"""Application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from app.settings.storage import SettingsStorage
from app.ui.main_window import MainWindow
from app.ui.start_screen import StartScreen
from app.ui.theme import ThemeManager


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    ThemeManager().apply(app, font_point_size=10)
    settings = SettingsStorage(Path.home() / ".vox")
    start = StartScreen()
    if start.exec() != QtWidgets.QDialog.Accepted:
        return 0
    project_path = Path.cwd() / "default.voxproj"
    window = MainWindow(project_path, settings)
    window.apply_preset(start.selection.preset_key)
    if not window.timeline.tracks:
        window.timeline.add_track("Track 1", "#4caf50")
        window.timeline.add_track("Track 2", "#42a5f5")
        window.timeline_widget.refresh()
    window.show()
    return app.exec()
main


if __name__ == "__main__":
    sys.exit(main())
