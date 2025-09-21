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


if __name__ == "__main__":
    sys.exit(main())
