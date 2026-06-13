"""Application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.settings.storage import SettingsStorage
from app.ui.main_window import MainWindow
from app.ui.palette import TRACK_COLORS
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
    window = MainWindow(project_path, settings, mode=start.selection.mode)
    window.apply_preset(start.selection.preset_key)
    if not window.timeline.tracks:
        window.timeline.add_track("Voice", TRACK_COLORS[0])
        window.timeline.add_track("Room Tone", TRACK_COLORS[1])
        window.arrange_view.refresh()

    geometry_hex = settings.get_option("ui", "geometry")
    if isinstance(geometry_hex, str) and geometry_hex:
        try:
            geometry = QtCore.QByteArray.fromHex(geometry_hex.encode("ascii"))
            if not geometry.isEmpty():
                window.restoreGeometry(geometry)
        except (TypeError, ValueError):
            pass

    window.show()
    exit_code = app.exec()

    settings.set_option("ui", "geometry", bytes(window.saveGeometry().toHex()).decode("ascii"))
    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
