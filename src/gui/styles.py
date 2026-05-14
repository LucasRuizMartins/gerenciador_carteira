"""
Tema visual global da aplicação — dark mode premium.
"""
from __future__ import annotations

COLORS = {
    "bg":           "#0f1117",
    "surface":      "#1a1d2e",
    "surface_alt":  "#242840",
    "accent":       "#7c6aff",
    "accent_hover": "#9d8fff",
    "accent_press": "#5a4bd1",
    "text":         "#e8eaf6",
    "text_muted":   "#9e9eb3",
    "success":      "#4caf82",
    "warning":      "#f0a500",
    "error":        "#f05252",
    "border":       "#2e3052",
    "border_focus": "#7c6aff",
}

GLOBAL_STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {COLORS["text"]};
    outline: none;
}}

QApplication, QMainWindow {{
    background-color: {COLORS["bg"]};
}}

QWidget {{
    background-color: transparent;
}}

QMainWindow {{
    background-color: {COLORS["bg"]};
}}

QFrame#sidebar {{
    background-color: {COLORS["surface"]};
    border-right: 1px solid {COLORS["border"]};
    min-width: 200px;
    max-width: 200px;
}}

QPushButton#nav_btn {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    color: {COLORS["text_muted"]};
    margin: 2px 8px;
}}
QPushButton#nav_btn:hover {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {COLORS["accent"]};
    color: white;
    font-weight: 600;
}}

QLabel#sidebar_title {{
    font-size: 15px;
    font-weight: 700;
    color: {COLORS["accent"]};
    padding: 20px 16px 8px 16px;
    letter-spacing: 0.5px;
}}

QLabel#sidebar_subtitle {{
    font-size: 11px;
    color: {COLORS["text_muted"]};
    padding: 0 16px 20px 16px;
}}

QFrame#content_area {{
    background-color: {COLORS["bg"]};
}}

QLabel#page_title {{
    font-size: 22px;
    font-weight: 700;
    color: {COLORS["text"]};
    padding: 0;
    margin-bottom: 4px;
}}

QLabel#page_subtitle {{
    font-size: 13px;
    color: {COLORS["text_muted"]};
    padding: 0;
    margin-bottom: 20px;
}}

QFrame#card {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 12px;
}}

QFrame#card:hover {{
    border-color: {COLORS["accent"]};
}}

QPushButton {{
    background-color: {COLORS["accent"]};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {COLORS["accent_hover"]};
}}
QPushButton:pressed {{
    background-color: {COLORS["accent_press"]};
}}
QPushButton:disabled {{
    background-color: {COLORS["border"]};
    color: {COLORS["text_muted"]};
}}

QPushButton#btn_secondary {{
    background-color: transparent;
    color: {COLORS["accent"]};
    border: 1px solid {COLORS["accent"]};
}}
QPushButton#btn_secondary:hover {{
    background-color: {COLORS["surface_alt"]};
}}

QPushButton#btn_danger {{
    background-color: transparent;
    color: {COLORS["error"]};
    border: 1px solid {COLORS["error"]};
}}
QPushButton#btn_danger:hover {{
    background-color: rgba(240, 82, 82, 0.1);
}}

QPushButton#btn_ghost {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text"]};
    border: none;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#btn_ghost:hover {{
    background-color: {COLORS["border"]};
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 4px 12px;
    min-height: 30px;
    font-size: 13px;
    color: {COLORS["text"]};
    selection-background-color: {COLORS["accent"]};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {COLORS["accent"]};
}}
QLineEdit::placeholder {{
    color: {COLORS["text_muted"]};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS["surface_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    selection-background-color: {COLORS["accent"]};
    font-size: 13px;
}}

QTableWidget {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    gridline-color: {COLORS["border"]};
    selection-background-color: rgba(124, 106, 255, 0.2);
}}
QTableWidget::item {{
    padding: 8px 12px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: rgba(124, 106, 255, 0.25);
    color: {COLORS["text"]};
}}
QHeaderView::section {{
    background-color: {COLORS["surface_alt"]};
    color: {COLORS["text_muted"]};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
}}

QPlainTextEdit#log_panel {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 12px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    color: {COLORS["text"]};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS["border"]};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS["text_muted"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QStatusBar {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_muted"]};
    border-top: 1px solid {COLORS["border"]};
    font-size: 11px;
    padding: 4px 12px;
}}

QProgressBar {{
    background-color: {COLORS["surface_alt"]};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS["accent"]}, stop:1 {COLORS["accent_hover"]});
    border-radius: 4px;
}}

QDialog {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
}}

QTabWidget::pane {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {COLORS["text_muted"]};
    padding: 8px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {COLORS["accent"]};
    border-bottom: 2px solid {COLORS["accent"]};
    font-weight: 600;
}}

QListWidget {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    outline: none;
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 4px;
}}
QListWidget::item:selected {{
    background-color: {COLORS["accent"]};
    color: white;
}}
"""
