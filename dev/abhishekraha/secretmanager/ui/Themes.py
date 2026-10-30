"""
Stylesheets and color palettes for Modern PySide6 UI.
Engineered with the sleek Slate 900 / Sky 400 design system.
Supports Dark Mode and Light Mode.
"""

DARK_THEME_QSS = """
/* Base Window & Global Typography */
QMainWindow, QWidget#CentralWidget, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #f8fafc;
}

/* Sidebar Navigation Pane */
QFrame#SidebarFrame {
    background-color: #131c2e;
    border-right: 1px solid #1e293b;
}

QListWidget#NavList {
    background-color: transparent;
    border: none;
    color: #94a3b8;
    outline: none;
}

QListWidget#NavList::item {
    height: 38px;
    padding-left: 14px;
    border-radius: 8px;
    margin: 2px 8px;
    color: #cbd5e1;
    font-size: 13px;
    font-weight: 500;
}

QListWidget#NavList::item:hover {
    background-color: #1e293b;
    color: #f8fafc;
}

QListWidget#NavList::item:selected {
    background-color: #0284c7;
    color: #ffffff;
    font-weight: 600;
}

/* Item List Pane */
QFrame#ItemListFrame {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

QLineEdit, QLineEdit#SearchBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-size: 13px;
    selection-background-color: #38bdf8;
    selection-color: #0f172a;
}

QLineEdit:focus, QLineEdit#SearchBox:focus {
    border: 1px solid #38bdf8;
    background-color: #1a2436;
}

QTextEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-size: 13px;
}

QTextEdit:focus {
    border: 1px solid #38bdf8;
}

QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    color: #f8fafc;
    font-size: 13px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

/* Secrets List Items */
QListWidget#SecretListWidget {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
}

QListWidget#SecretListWidget::item {
    background-color: #182234;
    border: 1px solid #273549;
    border-radius: 8px;
    margin-bottom: 6px;
    padding: 10px 12px;
}

QListWidget#SecretListWidget::item:hover {
    background-color: #1e293b;
    border-color: #38bdf8;
}

QListWidget#SecretListWidget::item:selected {
    background-color: #0f2b48;
    border: 1px solid #38bdf8;
}

/* Detail Panel */
QFrame#DetailFrame {
    background-color: #0f172a;
}

/* Buttons */
QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #273549;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton#PrimaryButton, QPushButton#AddSecretBtn {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover, QPushButton#AddSecretBtn:hover {
    background-color: #0369a1;
}

QPushButton#SuccessButton {
    background-color: #059669;
    color: #ffffff;
    border: none;
}

QPushButton#SuccessButton:hover {
    background-color: #047857;
}

QPushButton#DangerButton {
    background-color: #e11d48;
    color: #ffffff;
    border: none;
}

QPushButton#DangerButton:hover {
    background-color: #be123c;
}

/* Status Bar */
QStatusBar {
    background-color: #0b1120;
    color: #94a3b8;
    border-top: 1px solid #1e293b;
    font-size: 11px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0px 0px 0px 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

LIGHT_THEME_QSS = """
/* Light Theme fallback with crisp slate borders */
QMainWindow, QWidget#CentralWidget, QDialog {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QFrame#SidebarFrame {
    background-color: #f1f5f9;
    border-right: 1px solid #e2e8f0;
}

QFrame#ItemListFrame {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
}

QLineEdit, QLineEdit#SearchBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 12px;
    color: #0f172a;
}

QPushButton {
    background-color: #f1f5f9;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
}
"""
