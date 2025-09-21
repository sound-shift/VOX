# -*- coding: utf-8 -*-
"""
widgets.py — shared UI helpers for UnifyAudio
- apply_dark_theme
- make_tile
(без изменений)
"""
from __future__ import annotations
from PySide6 import QtWidgets, QtGui, QtCore


def apply_dark_theme(app: QtWidgets.QApplication, base_font_point_size: int = 9):
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor(18, 20, 24))
    pal.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor(12, 14, 18))
    pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(18, 20, 24))
    pal.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    pal.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    pal.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    pal.setColor(QtGui.QPalette.Button, QtGui.QColor(28, 32, 38))
    pal.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    pal.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#4caf50"))
    pal.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(pal)

    font = app.font()
    font.setPointSize(base_font_point_size)
    app.setFont(font)
    app.setStyle("Fusion")


def make_tile(title: str, body: QtWidgets.QWidget, collapsible: bool = True, collapsed: bool = False) -> QtWidgets.QWidget:
    wrapper = QtWidgets.QWidget(body.parent() if body.parent() else None)
    v = QtWidgets.QVBoxLayout(wrapper)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    head = QtWidgets.QToolButton(wrapper)
    head.setText(title)
    head.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
    head.setCheckable(collapsible)
    head.setChecked(not collapsed)
    head.setStyleSheet("""
        QToolButton {
            background: #22262c; color: #e0e0e0; border: 1px solid #2d333b; padding: 4px 6px; text-align: left;
            font-weight: 600; font-size: 10pt;
        }
        QToolButton:checked { background: #263238; }
    """)
    body_holder = QtWidgets.QWidget(wrapper)
    vb = QtWidgets.QVBoxLayout(body_holder)
    vb.setContentsMargins(6, 6, 6, 6)
    vb.setSpacing(6)
    body.setParent(body_holder)
    vb.addWidget(body)

    if collapsible:
        body_holder.setVisible(not collapsed)
        head.toggled.connect(body_holder.setVisible)

    v.addWidget(head)
    v.addWidget(body_holder)

    wrapper.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
    return wrapper