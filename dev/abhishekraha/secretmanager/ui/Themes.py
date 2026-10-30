"""
Stylesheets and color palettes for Modern PySide6 UI.
Engineered for high contrast, crisp legibility, and modern aesthetic.
Supports Dark Mode and Light Mode.
"""

DARK_THEME_QSS = """
/* Base Window & Global Typography */
QMainWindow, QWidget#CentralWidget, QDialog {
    background-color: #12151C;
    color: #F1F5F9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #F1F5F9;
}

/* Sidebar Navigation Pane */
QFrame#SidebarFrame {
    background-color: #161A23;
    border-right: 1px solid #232936;
}

QListWidget#NavList {
    background-color: transparent;
    border: none;
    color: #A0ABC0;
    outline: none;
}

QListWidget#NavList::item {
    height: 38px;
    padding-left: 14px;
    border-radius: 6px;
    margin: 2px 8px;
    color: #CBD5E1;
    font-size: 13px;
    font-weight: 500;
}

QListWidget#NavList::item:hover {
    background-color: #232936;
    color: #FFFFFF;
}

QListWidget#NavList::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
    font-weight: bold;
}

/* Item List Pane */
QFrame#ItemListFrame {
    background-color: #131720;
    border-right: 1px solid #232936;
}

QLineEdit, QLineEdit#SearchBox {
    background-color: #1A1F2C;
    border: 1px solid #333F54;
    border-radius: 6px;
    padding: 8px 12px;
    color: #FFFFFF;
    font-size: 13px;
    selection-background-color: #2563EB;
}

QLineEdit:focus, QLineEdit#SearchBox:focus {
    border: 1px solid #3B82F6;
    background-color: #1E2433;
}

QTextEdit {
    background-color: #1A1F2C;
    border: 1px solid #333F54;
    border-radius: 6px;
    padding: 8px 12px;
    color: #FFFFFF;
    font-size: 13px;
}

QTextEdit:focus {
    border: 1px solid #3B82F6;
}

QComboBox {
    background-color: #1A1F2C;
    border: 1px solid #333F54;
    border-radius: 6px;
    padding: 6px 12px;
    color: #FFFFFF;
    font-size: 13px;
}

QComboBox QAbstractItemView {
    background-color: #1A1F2C;
    border: 1px solid #333F54;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    color: #FFFFFF;
}

/* Secret List Cards */
QListWidget#SecretListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#SecretListWidget::item {
    background-color: #1A1F2C;
    border: 1px solid #273142;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 4px 8px;
    color: #FFFFFF;
    font-size: 13px;
}

QListWidget#SecretListWidget::item:hover {
    border: 1px solid #3B82F6;
    background-color: #202738;
}

QListWidget#SecretListWidget::item:selected {
    background-color: #1E293B;
    border: 1.5px solid #60A5FA;
    color: #FFFFFF;
}

/* Detail Panel */
QFrame#DetailFrame {
    background-color: #12151C;
}

QLabel {
    color: #F1F5F9;
}

QLabel#DetailTitle {
    font-size: 22px;
    font-weight: bold;
    color: #FFFFFF;
}

QLabel#DetailSubtitle {
    font-size: 13px;
    color: #94A3B8;
}

/* Group Boxes with High Contrast Borders */
QGroupBox {
    border: 1px solid #2D3748;
    background-color: #161A24;
    border-radius: 8px;
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    font-weight: bold;
    color: #38BDF8;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    background-color: #12151C;
    border-radius: 4px;
}

/* Buttons */
QPushButton {
    background-color: #222938;
    color: #F8FAFC;
    border: 1px solid #3B465E;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2F394D;
    border: 1px solid #4B5975;
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #3B4761;
}

QPushButton:disabled {
    background-color: #181D26;
    border: 1px solid #232936;
    color: #4B5563;
}

QPushButton#PrimaryButton {
    background-color: #2563EB;
    border: 1px solid #3B82F6;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton#PrimaryButton:hover {
    background-color: #1D4ED8;
    border: 1px solid #60A5FA;
}

QPushButton#DangerButton {
    background-color: #991B1B;
    border: 1px solid #DC2626;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton#DangerButton:hover {
    background-color: #B91C1C;
    border: 1px solid #EF4444;
}

/* Progress Bars */
QProgressBar {
    background-color: #1E2433;
    border: 1px solid #2D3748;
    border-radius: 4px;
    height: 10px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #10B981;
    border-radius: 4px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #12151C;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #2D3748;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4B5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

LIGHT_THEME_QSS = """
/* Base Window & Global Typography */
QMainWindow, QWidget#CentralWidget, QDialog {
    background-color: #F8FAFC;
    color: #0F172A;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #0F172A;
}

/* Sidebar Navigation Pane */
QFrame#SidebarFrame {
    background-color: #EDF2F7;
    border-right: 1px solid #CBD5E1;
}

QListWidget#NavList {
    background-color: transparent;
    border: none;
    color: #475569;
    outline: none;
}

QListWidget#NavList::item {
    height: 38px;
    padding-left: 14px;
    border-radius: 6px;
    margin: 2px 8px;
    color: #334155;
    font-size: 13px;
    font-weight: 500;
}

QListWidget#NavList::item:hover {
    background-color: #E2E8F0;
    color: #0F172A;
}

QListWidget#NavList::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
    font-weight: bold;
}

/* Item List Pane */
QFrame#ItemListFrame {
    background-color: #F1F5F9;
    border-right: 1px solid #CBD5E1;
}

QLineEdit, QLineEdit#SearchBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 12px;
    color: #0F172A;
    font-size: 13px;
}

QLineEdit:focus, QLineEdit#SearchBox:focus {
    border: 1px solid #2563EB;
}

QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 12px;
    color: #0F172A;
    font-size: 13px;
}

QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 12px;
    color: #0F172A;
    font-size: 13px;
}

/* Secret List Cards */
QListWidget#SecretListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#SecretListWidget::item {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 4px 8px;
    color: #0F172A;
}

QListWidget#SecretListWidget::item:hover {
    border: 1px solid #93C5FD;
    background-color: #F8FAFC;
}

QListWidget#SecretListWidget::item:selected {
    background-color: #EFF6FF;
    border: 1.5px solid #2563EB;
    color: #1E3A8A;
}

/* Detail Panel */
QFrame#DetailFrame {
    background-color: #F8FAFC;
}

QLabel {
    color: #0F172A;
}

QLabel#DetailTitle {
    font-size: 22px;
    font-weight: bold;
    color: #0F172A;
}

QLabel#DetailSubtitle {
    font-size: 13px;
    color: #64748B;
}

QGroupBox {
    border: 1px solid #CBD5E1;
    background-color: #FFFFFF;
    border-radius: 8px;
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    font-weight: bold;
    color: #1D4ED8;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    background-color: #F8FAFC;
}

QPushButton {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #F1F5F9;
    border: 1px solid #94A3B8;
}

QPushButton#PrimaryButton {
    background-color: #2563EB;
    border: 1px solid #1D4ED8;
    color: #FFFFFF;
}

QPushButton#PrimaryButton:hover {
    background-color: #1D4ED8;
}

QPushButton#DangerButton {
    background-color: #DC2626;
    border: 1px solid #B91C1C;
    color: #FFFFFF;
}

QPushButton#DangerButton:hover {
    background-color: #B91C1C;
}
"""
