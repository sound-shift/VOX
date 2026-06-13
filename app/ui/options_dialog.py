"""Application preferences dialog."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.settings.storage import DEFAULT_HOTKEYS, SettingsStorage


class OptionsDialog(QtWidgets.QDialog):
    def __init__(self, settings: SettingsStorage, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("VOX Preferences")
        self.resize(520, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget(self)

        autosave_tab = QtWidgets.QWidget()
        autosave_layout = QtWidgets.QFormLayout(autosave_tab)
        self.spin_interval = QtWidgets.QSpinBox()
        self.spin_interval.setRange(30, 3600)
        self.spin_interval.setSuffix(" sec")
        self.spin_interval.setValue(int(self.settings.get_option("autosave", "interval_sec", 300)))
        self.spin_slots = QtWidgets.QSpinBox()
        self.spin_slots.setRange(3, 20)
        self.spin_slots.setValue(int(self.settings.get_option("autosave", "slots", 5)))
        autosave_layout.addRow("Autosave interval", self.spin_interval)
        autosave_layout.addRow("Autosave slots", self.spin_slots)
        tabs.addTab(autosave_tab, "Autosave")

        hotkeys_tab = QtWidgets.QWidget()
        hotkeys_layout = QtWidgets.QFormLayout(hotkeys_tab)
        self._hotkey_edits: dict[str, QtWidgets.QLineEdit] = {}
        bindings = self.settings.hotkey_bindings()
        for action, default in DEFAULT_HOTKEYS.items():
            edit = QtWidgets.QLineEdit(bindings.get(action, default))
            hotkeys_layout.addRow(action.replace("_", " ").title(), edit)
            self._hotkey_edits[action] = edit
        tabs.addTab(hotkeys_tab, "Hotkeys")

        layout.addWidget(tabs)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        self.settings.set_option("autosave", "interval_sec", self.spin_interval.value())
        self.settings.set_option("autosave", "slots", self.spin_slots.value())
        for action, edit in self._hotkey_edits.items():
            self.settings.set_hotkey(action, edit.text().strip() or DEFAULT_HOTKEYS[action])
        self.accept()


__all__ = ["OptionsDialog"]
