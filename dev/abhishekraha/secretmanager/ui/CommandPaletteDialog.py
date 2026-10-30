"""
CommandPaletteDialog: Floating, frameless, keyboard-driven command palette for Simple Credential Manager.
Summonable via global hotkey (Ctrl+Shift+Space), auto-dismisses on focus loss or Escape,
and enables sub-second credential search and copy with high-contrast Slate 900 styling.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QGraphicsDropShadowEffect,
    QWidget,
    QFrame,
)

from dev.abhishekraha.secretmanager.core.TotpService import TotpService
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.utils.GlobalHotkeyService import get_active_screen_geometry
from dev.abhishekraha.secretmanager.utils.SecureClipboardManager import SecureClipboardManager


class CommandPaletteDialog(QDialog):
    """
    Floating command palette providing instant fuzzy/text search,
    one-key password copy, TOTP copy, and navigation to the full manager.
    Styled with the elegant Slate 900 / Sky 400 design system.
    """

    open_full_window_requested = Signal(str)

    def __init__(self, provider: VaultDataProvider, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.provider = provider
        self._all_records: list[Secret] = []

        # Configure window flags & translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(640)

        self._init_ui()
        self.reload_records()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(14, 14, 14, 14)

        # Container card for rounded corners and dark slate background
        self.container = QWidget(self)
        self.container.setObjectName("PaletteContainer")
        self.container.setStyleSheet("""
            QWidget#PaletteContainer {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 14px;
            }
        """)

        # Drop shadow effect (soft, ambient elevation)
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 210))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 16, 16, 14)
        container_layout.setSpacing(10)

        # Header Search Area
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)

        search_icon = QLabel("🔍", self.container)
        search_icon.setStyleSheet("font-size: 14px; color: #94a3b8;")
        search_layout.addWidget(search_icon)

        # Search Bar
        self.search_input = QLineEdit(self.container)
        self.search_input.setPlaceholderText("Search credentials by name, username, url...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 14px;
                selection-background-color: #38bdf8;
                selection-color: #0f172a;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #1a2436;
            }
        """)
        self.search_input.textChanged.connect(self._filter_results)
        search_layout.addWidget(self.search_input)

        hotkey_badge = QLabel("Ctrl+Shift+Space", self.container)
        hotkey_badge.setStyleSheet("""
            QLabel {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #94a3b8;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 6px;
            }
        """)
        search_layout.addWidget(hotkey_badge)

        container_layout.addLayout(search_layout)

        # Divider line
        divider = QFrame(self.container)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("border: none; border-top: 1px solid #1e293b;")
        container_layout.addWidget(divider)

        # Results List
        self.results_list = QListWidget(self.container)
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                color: #e2e8f0;
            }
            QListWidget::item {
                background-color: #182234;
                border: 1px solid #273549;
                padding: 8px 12px;
                border-radius: 8px;
                margin-bottom: 5px;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
                border-color: #38bdf8;
            }
            QListWidget::item:selected {
                background-color: #0f2b48;
                border: 1px solid #38bdf8;
                color: #ffffff;
                font-weight: 600;
            }
        """)
        self.results_list.itemDoubleClicked.connect(self.handle_primary_action)
        container_layout.addWidget(self.results_list)

        # Footer hints with keyboard shortcuts
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(6, 4, 6, 0)
        footer_layout.setSpacing(12)

        shortcut_hints = [
            ("↵", "Copy Password", "#10b981"),
            ("Ctrl+C", "Username", "#cbd5e1"),
            ("Ctrl+T", "TOTP Code", "#38bdf8"),
            ("Ctrl+O", "Full Details", "#a855f7"),
            ("Esc", "Dismiss", "#64748b"),
        ]

        for key, desc, col in shortcut_hints:
            hint_box = QHBoxLayout()
            hint_box.setSpacing(4)
            badge = QLabel(key, self.container)
            badge.setStyleSheet(f"background: #1e293b; color: {col}; font-weight: bold; font-size: 10px; padding: 2px 5px; border-radius: 4px; border: 1px solid #334155;")
            text = QLabel(desc, self.container)
            text.setStyleSheet("color: #64748b; font-size: 11px;")
            hint_box.addWidget(badge)
            hint_box.addWidget(text)
            footer_layout.addLayout(hint_box)

        footer_layout.addStretch()
        container_layout.addLayout(footer_layout)

        outer_layout.addWidget(self.container)

    def set_provider(self, provider: VaultDataProvider) -> None:
        """
        Updates the data provider (e.g. when switching between Local and Remote).
        """
        self.provider = provider
        self.reload_records()

    def reload_records(self) -> None:
        """
        Fetches fresh records from active provider and updates results list.
        """
        if self.provider and self.provider.is_unlocked():
            try:
                self._all_records = self.provider.get_secret_records()
            except Exception:
                self._all_records = []
        else:
            self._all_records = []
        self._filter_results(self.search_input.text())

    def _filter_results(self, text: str) -> None:
        query = text.strip().lower()
        self.results_list.clear()

        matched = []
        for secret in self._all_records:
            name = secret.get_name() if hasattr(secret, "get_name") else getattr(secret, "name", "")
            username = secret.get_username() if hasattr(secret, "get_username") else getattr(secret, "username", "")
            cat = secret.get_category() if hasattr(secret, "get_category") else getattr(secret, "category", "login")
            url = secret.get_url() if hasattr(secret, "get_url") else getattr(secret, "url", "")

            if not query:
                matched.append(secret)
            else:
                if (query in name.lower() or query in username.lower() or query in cat.lower() or query in url.lower()):
                    matched.append(secret)

        # Dynamic height sizing based on result count (max 8 visible items)
        visible_rows = min(max(len(matched), 1), 8)
        self.results_list.setFixedHeight(visible_rows * 48 + 10)

        for secret in matched[:20]:
            name = secret.get_name() if hasattr(secret, "get_name") else getattr(secret, "name", "")
            username = secret.get_username() if hasattr(secret, "get_username") else getattr(secret, "username", "")
            cat = secret.get_category() if hasattr(secret, "get_category") else getattr(secret, "category", "login")

            display_title = f"{name}"
            if username:
                display_title += f" ({username})"
            display_title += f" • {cat}"

            totp_sec = secret.get_totp_secret() if hasattr(secret, "get_totp_secret") else getattr(secret, "totp_secret", None)
            if totp_sec:
                display_title += " [2FA]"

            item = QListWidgetItem(display_title)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.results_list.addItem(item)

        if not matched:
            empty_item = QListWidgetItem("No matching credentials found")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_list.addItem(empty_item)
        else:
            self.results_list.setCurrentRow(0)

        self.adjustSize()

    def show_centered(self) -> None:
        """
        Positions palette centered horizontally in top third of active monitor.
        """
        self.search_input.clear()
        self.reload_records()

        screen_geo = get_active_screen_geometry()
        x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
        y = screen_geo.y() + (screen_geo.height() // 4)

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()

    def handle_primary_action(self) -> None:
        """Copies password of selected secret to clipboard with 30s auto-erase and dismisses."""
        current_item = self.results_list.currentItem()
        if not current_item:
            return

        secret_name = current_item.data(Qt.ItemDataRole.UserRole)
        if not secret_name:
            return

        secret = self._find_secret(secret_name)
        if secret:
            pwd = secret.get_password() if hasattr(secret, "get_password") else getattr(secret, "password", "")
            SecureClipboardManager.copy(pwd, clear_timeout_seconds=30)
            self.hide()

    def handle_copy_username(self) -> None:
        current_item = self.results_list.currentItem()
        if not current_item:
            return
        secret_name = current_item.data(Qt.ItemDataRole.UserRole)
        secret = self._find_secret(secret_name)
        if secret:
            user = secret.get_username() if hasattr(secret, "get_username") else getattr(secret, "username", "")
            if user:
                SecureClipboardManager.copy(user, clear_timeout_seconds=30)
                self.hide()

    def handle_copy_totp(self) -> None:
        current_item = self.results_list.currentItem()
        if not current_item:
            return
        secret_name = current_item.data(Qt.ItemDataRole.UserRole)
        secret = self._find_secret(secret_name)
        if secret:
            totp_sec = secret.get_totp_secret() if hasattr(secret, "get_totp_secret") else getattr(secret, "totp_secret", None)
            if totp_sec:
                try:
                    code = TotpService.generate_totp(totp_sec)
                    SecureClipboardManager.copy(code, clear_timeout_seconds=30)
                    self.hide()
                except Exception:
                    pass

    def _find_secret(self, name: str) -> Optional[Secret]:
        for s in self._all_records:
            sec_name = s.get_name() if hasattr(s, "get_name") else getattr(s, "name", "")
            if sec_name == name:
                return s
        return None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.handle_primary_action()
            event.accept()
        elif modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C:
            self.handle_copy_username()
            event.accept()
        elif modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_T:
            self.handle_copy_totp()
            event.accept()
        elif modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_O:
            current_item = self.results_list.currentItem()
            if current_item:
                sec_name = current_item.data(Qt.ItemDataRole.UserRole)
                if sec_name:
                    self.hide()
                    self.open_full_window_requested.emit(sec_name)
            event.accept()
        elif key == Qt.Key.Key_Down:
            curr = self.results_list.currentRow()
            if curr < self.results_list.count() - 1:
                self.results_list.setCurrentRow(curr + 1)
            event.accept()
        elif key == Qt.Key.Key_Up:
            curr = self.results_list.currentRow()
            if curr > 0:
                self.results_list.setCurrentRow(curr - 1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                self.hide()
        super().changeEvent(event)
