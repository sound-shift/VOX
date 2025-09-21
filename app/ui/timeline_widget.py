"""Simple timeline view for the MVP."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.timeline.model import Timeline


class TimelineWidget(QtWidgets.QTreeWidget):
    def __init__(self, timeline: Timeline, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.timeline = timeline
        self.setColumnCount(2)
        self.setHeaderLabels(["Track", "Clips"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)
        self.refresh()

    def refresh(self) -> None:
        self.clear()
        for track in self.timeline.tracks.values():
            item = QtWidgets.QTreeWidgetItem([track.name, str(len(track.clips))])
            color = QtGui.QColor(track.color)
            item.setBackground(0, QtGui.QBrush(color))
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("white")))
            self.addTopLevelItem(item)


__all__ = ["TimelineWidget"]
