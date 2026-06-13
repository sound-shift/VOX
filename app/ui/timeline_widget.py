"""Simple timeline view for the MVP."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.timeline.model import Timeline


class TimelineWidget(QtWidgets.QTreeWidget):
    trackSelected = QtCore.Signal(int)

    def __init__(self, timeline: Timeline, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.timeline = timeline
        self.selected_track_id: int | None = None
        self.setColumnCount(3)
        self.setHeaderLabels(["Track", "Clips", "Armed"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.refresh()

    def refresh(self) -> None:
        self.blockSignals(True)
        self.clear()
        for track in self.timeline.tracks.values():
            armed = "●" if track.armed else ""
            item = QtWidgets.QTreeWidgetItem([track.name, str(len(track.clips)), armed])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, track.id)
            color = QtGui.QColor(track.color)
            item.setBackground(0, QtGui.QBrush(color))
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("white")))
            self.addTopLevelItem(item)
        if self.topLevelItemCount() and self.selected_track_id is None:
            self.topLevelItem(0).setSelected(True)
        self.blockSignals(False)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        item = self.currentItem()
        if item is None:
            return
        track_id = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(track_id, int):
            self.selected_track_id = track_id
            self.trackSelected.emit(track_id)


__all__ = ["TimelineWidget"]
