"""Global Qt stylesheets for VOX."""
from __future__ import annotations

from app.ui.palette import (
    ACCENT_ARM,
    ACCENT_BLUE,
    ACCENT_ORANGE,
    BG_DEEP,
    BG_HEADER,
    BG_PANEL,
    BG_RAISED,
    BG_TRANSPORT,
    BORDER,
    BORDER_LIGHT,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

APP_STYLESHEET = f"""
QMainWindow, QDialog {{
    background: {BG_DEEP};
    color: {TEXT_PRIMARY};
}}
QMenuBar {{
    background: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0;
}}
QMenuBar::item:selected {{
    background: {BG_RAISED};
}}
QMenu {{
    background: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background: {ACCENT_BLUE};
    color: #000;
}}
QStatusBar {{
    background: {BG_TRANSPORT};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
}}
QToolBar {{
    background: transparent;
    border: none;
    spacing: 6px;
}}
QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}
QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar:horizontal {{
    background: {BG_DEEP};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-width: 24px;
}}
QComboBox, QLineEdit, QSpinBox {{
    background: {BG_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_BLUE};
    selection-color: #000;
}}
QPushButton {{
    background: {BG_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {BG_HEADER};
    border-color: {BORDER_LIGHT};
}}
QPushButton:pressed {{
    background: {BG_PANEL};
}}
QPushButton:checked {{
    background: {ACCENT_ARM};
    color: #000;
    border-color: {ACCENT_ARM};
}}
QPushButton#primaryBtn {{
    background: {ACCENT_ORANGE};
    color: #111;
    border: none;
}}
QPushButton#primaryBtn:hover {{
    background: #ff8a65;
}}
QGroupBox {{
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {TEXT_DIM};
}}
QLabel#sectionTitle {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
"""
