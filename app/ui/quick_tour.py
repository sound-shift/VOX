"""First-run quick tour — four screens, no code reading required."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.ui import palette

PAGES = [
    (
        "Welcome to VOX",
        "Record and polish voice-over: podcasts, audiobooks, and ADR (dub to picture).\n\n"
        "Pick a workflow on the start screen — ADR adds video preview and Dialog track.",
    ),
    (
        "Timeline & transport",
        "• Click the timeline to move the playhead\n"
        "• R = arm track, * = record, Space = play\n"
        "• B = blade (split), M = marker\n"
        "• [ and ] = loop in/out, \\ = toggle loop",
    ),
    (
        "Channel Strip (right panel)",
        "• Capture @ Playhead — noise print for denoise\n"
        "• Match EQ — set reference or use Picture Lock (ADR)\n"
        "• Isolate — HPSS or ML (Demucs) if installed\n"
        "• Ctrl+Z / Ctrl+Shift+Z — undo / redo",
    ),
    (
        "ADR workflow",
        "1. Import Video (Picture Lock panel)\n"
        "2. Click video to scrub playhead\n"
        "3. Capture noise at a pause\n"
        "4. Arm Dialog → record while watching picture\n"
        "5. Punch-in overwrites loop region only\n"
        "6. Click take lanes (A/B/C) to comp",
    ),
]


class QuickTour(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VOX — Quick tour")
        self.setMinimumWidth(480)
        self._index = 0
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        self.title = QtWidgets.QLabel(PAGES[0][0])
        self.title.setStyleSheet(
            f"color: {palette.TEXT_PRIMARY}; font-size: 16px; font-weight: 700;"
        )
        self.body = QtWidgets.QLabel(PAGES[0][1])
        self.body.setWordWrap(True)
        self.body.setStyleSheet(f"color: {palette.TEXT_SECONDARY}; font-size: 12px;")
        self.dots = QtWidgets.QLabel("● ○ ○ ○")
        self.dots.setStyleSheet(f"color: {palette.ACCENT_VIOLET};")
        self.dots.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addStretch(1)
        layout.addWidget(self.dots)

        row = QtWidgets.QHBoxLayout()
        self.btn_skip = QtWidgets.QPushButton("Skip")
        self.btn_back = QtWidgets.QPushButton("Back")
        self.btn_next = QtWidgets.QPushButton("Next")
        self.btn_back.setEnabled(False)
        self.btn_skip.clicked.connect(self.reject)
        self.btn_back.clicked.connect(self._back)
        self.btn_next.clicked.connect(self._next)
        row.addWidget(self.btn_skip)
        row.addStretch(1)
        row.addWidget(self.btn_back)
        row.addWidget(self.btn_next)
        layout.addLayout(row)

    def _update_page(self) -> None:
        title, body = PAGES[self._index]
        self.title.setText(title)
        self.body.setText(body)
        dots = ["○"] * len(PAGES)
        dots[self._index] = "●"
        self.dots.setText(" ".join(dots))
        self.btn_back.setEnabled(self._index > 0)
        self.btn_next.setText("Done" if self._index == len(PAGES) - 1 else "Next")

    def _back(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._update_page()

    def _next(self) -> None:
        if self._index >= len(PAGES) - 1:
            self.accept()
            return
        self._index += 1
        self._update_page()


def maybe_show_tour(settings, parent: QtWidgets.QWidget) -> None:
    if settings.get_option("ui", "tour_completed"):
        return
    tour = QuickTour(parent)
    if tour.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        settings.set_option("ui", "tour_completed", True)
    else:
        settings.set_option("ui", "tour_completed", True)


__all__ = ["QuickTour", "maybe_show_tour"]
