"""Application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.dsp.workflows import get_workflow
from app.settings.storage import SettingsStorage
from app.ui.main_window import MainWindow
from app.ui.palette import TRACK_COLORS
from app.ui.start_screen import StartScreen
from app.ui.quick_tour import maybe_show_tour
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
    window.apply_workflow(start.selection.mode)
    if start.selection.preset_key != get_workflow(start.selection.mode).preset_key:
        window.apply_preset(start.selection.preset_key)
    if not window.timeline.tracks:
        if start.selection.mode == "adr":
            window.timeline.add_track("Dialog", TRACK_COLORS[0])
            window.timeline.add_track("Picture Lock", TRACK_COLORS[2])
        else:
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
    maybe_show_tour(settings, window)
    exit_code = app.exec()

    settings.set_option("ui", "geometry", bytes(window.saveGeometry().toHex()).decode("ascii"))
    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
