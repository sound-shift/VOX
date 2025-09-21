# -*- coding: utf-8 -*-
"""
controls.py — reusable UI controls for UnifyAudio
- Knob: compact dial with title, value, units, and hint
- EqPreview: preview of Tilt + Bass-Guard + Match weight
r9.4.3: без изменений API; крутилки допускают одинаковую ширину через setFixedWidth извне
"""
from __future__ import annotations
from typing import Optional
from PySide6 import QtWidgets, QtGui, QtCore
import math


class Knob(QtWidgets.QWidget):
    valueChanged = QtCore.Signal(float)
    hovered = QtCore.Signal(str)

    def __init__(self, title: str, vmin: float, vmax: float, step: float, unit: str = "", value: Optional[float] = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._vmin = float(vmin)
        self._vmax = float(vmax)
        self._step = float(step) if step > 0 else 1.0
        self._steps = max(1, int(round((self._vmax - self._vmin) / self._step)))
        self._hint_text = ""

        self.dial = QtWidgets.QDial(self)
        self.dial.setNotchesVisible(True)
        self.dial.setWrapping(False)
        self.dial.setRange(0, self._steps)
        self.dial.setFixedSize(84, 84)

        self.lab_title = QtWidgets.QLabel(title, self)
        self.lab_title.setAlignment(QtCore.Qt.AlignCenter)
        self.lab_value = QtWidgets.QLabel("", self)
        self.lab_value.setAlignment(QtCore.Qt.AlignCenter)
        f = self.lab_title.font()
        f.setPointSize(max(8, f.pointSize()-1))
        self.lab_title.setFont(f)
        self.lab_value.setFont(f)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        lay.addWidget(self.lab_title)
        lay.addWidget(self.dial, alignment=QtCore.Qt.AlignCenter)
        lay.addWidget(self.lab_value)

        self.dial.valueChanged.connect(self._on_dial)
        if value is None:
            value = self._vmin
        self.setValue(float(value))

        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.setStyleSheet("QDial { background: transparent; }")

    def setHint(self, text: str):
        self._hint_text = text

    def enterEvent(self, e: QtCore.QEvent):
        if self._hint_text:
            self.hovered.emit(self._hint_text)
        else:
            self.hovered.emit(self._title)
        super().enterEvent(e)

    def _fmt(self, x: float) -> str:
        if self._step >= 1.0:
            return f"{int(round(x))}{self._unit}"
        if self._vmax <= 1.0 or self._step < 0.1:
            return f"{x:.2f}{self._unit}"
        return f"{x:.1f}{self._unit}"

    def _on_dial(self, raw: int):
        v = self._vmin + raw * self._step
        v = min(max(v, self._vmin), self._vmax)
        self.lab_value.setText(self._fmt(v))
        self.valueChanged.emit(v)

    def value(self) -> float:
        raw = self.dial.value()
        v = self._vmin + raw * self._step
        return min(max(v, self._vmin), self._vmax)

    def setValue(self, v: float):
        v = min(max(v, self._vmin), self._vmax)
        raw = int(round((v - self._vmin) / self._step))
        self.dial.blockSignals(True)
        self.dial.setValue(raw)
        self.dial.blockSignals(False)
        self.lab_value.setText(self._fmt(v))


class EqPreview(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self._tilt_db_oct = 0.0
        self._bass_fc = 140.0
        self._bass_max = 1.5
        self._weight = 1.0  # 0..1

    def setParams(self, tilt_db_oct: float, bass_fc: float, bass_max: float, weight: float):
        self._tilt_db_oct = float(tilt_db_oct)
        self._bass_fc = float(bass_fc)
        self._bass_max = float(bass_max)
        self._weight = float(weight)
        self.update()

    def paintEvent(self, e: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(10, 8, -10, -8)
        p.fillRect(self.rect(), QtGui.QColor("#14171b"))
        p.setPen(QtGui.QPen(QtGui.QColor("#2a2e33"), 1)); p.drawRect(r)

        def x_of_f(f):
            import math
            f = max(20.0, min(20000.0, f))
            t = (math.log10(f) - math.log10(20.0)) / (math.log10(20000.0) - math.log10(20.0))
            return r.left() + t * r.width()

        y_mid = r.center().y()
        p.setPen(QtGui.QPen(QtGui.QColor("#2f3338"), 1, QtCore.Qt.DashLine))
        p.drawLine(r.left(), y_mid, r.right(), y_mid)

        tilt = self._tilt_db_oct
        span_oct = 10.0
        total_db = tilt * span_oct
        db_to_px = (r.height() * 0.8) / 12.0
        y_low = y_mid + (total_db / 2.0) * db_to_px
        y_high = y_mid - (total_db / 2.0) * db_to_px

        fc_x = x_of_f(self._bass_fc)
        p.fillRect(QtCore.QRectF(r.left(), r.top(), fc_x - r.left(), r.height()), QtGui.QColor(76, 175, 80, 28))
        p.setPen(QtGui.QPen(QtGui.QColor("#4caf50"), 2)); p.drawLine(fc_x, r.bottom() - 10, fc_x, r.bottom())
        p.setPen(QtGui.QPen(QtGui.QColor("#8bd28e"), 2)); p.drawText(fc_x + 4, r.bottom() - 2, f"+{self._bass_max:.1f} dB")

        p.setPen(QtGui.QPen(QtGui.QColor("#66bb6a"), 2)); p.drawLine(r.left(), y_low, r.right(), y_high)

        p.setPen(QtGui.QPen(QtGui.QColor("#9aa0a6")))
        p.drawText(r.adjusted(6, 6, -6, -6), QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft, f"Match weight: {int(round(self._weight * 100))}%")
        p.drawText(r.left(), r.bottom() + 14, "20 Hz"); p.drawText(r.right() - 40, r.bottom() + 14, "20 kHz")
        p.end()