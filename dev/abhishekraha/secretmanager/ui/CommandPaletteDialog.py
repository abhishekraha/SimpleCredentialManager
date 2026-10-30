"""
CommandPaletteDialog: Floating, frameless, keyboard-driven command palette for Simple Credential Manager.
Summonable via a global hotkey, auto-dismisses on focus loss or Escape,
and enables sub-second credential search and copy.
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
    """

    open_full_window_requested = Signal(str)

    def __init__(self, provider: VaultDataProvider, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.provider = provider
        self._all_records: list[Secret] = []

        # Configure window flags & translucent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(600)

        self._init_ui()
        self.reload_records()

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        # Container card for rounded corners and dark slate background
        self.container = QWidget(self)
        self.container.setObjectName("PaletteContainer")
        self.container.setStyleSheet("""
            QWidget#PaletteContainer {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(14, 14, 14, 14)
        container_layout.setSpacing(10)

        # Search Bar
        self.search_input = QLineEdit(self.container)
        self.search_input.setPlaceholderText("Search credentials... (Enter: Copy Password, Ctrl+C: Username, Ctrl+T: TOTP)")
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
            }
        """)
        self.search_input.textChanged.connect(self._filter_results)
        container_layout.addWidget(self.search_input)

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
                padding: 8px 12px;
                border-radius: 6px;
                margin-bottom: 3px;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 600;
            }
        """)
        self.results_list.itemDoubleClicked.connect(self.handle_primary_action)
        container_layout.addWidget(self.results_list)

        # Footer hints
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(4, 0, 4, 0)
        footer_label = QLabel("↵ Copy Password   Ctrl+C Username   Ctrl+T TOTP   Ctrl+O Open Full   Esc Dismiss", self.container)
        footer_label.setStyleSheet("color: #64748b; font-size: 11px;")
        footer_layout.addWidget(footer_label)
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
        Fetches fresh records from the active provider if unlocked and updates results list.
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
            if not query:
                matched.append(secret)
            else:
                name_match = query in secret.name.lower()
                user_match = query in (secret.username or "").lower()
                cat_match = query in (secret.category or "").lower()
                url_match = query in (secret.url or "").lower()
                if name_match or user_match or cat_match or url_match:
                    matched.append(secret)

        for secret in matched[:50]:  # Limit top 50 matches for responsiveness
            user_part = f" ({secret.username})" if secret.username else ""
            totp_badge = " [2FA]" if secret.has_totp() else ""
            cat_badge = f" • {secret.category}" if secret.category else ""
            label_text = f"{secret.name}{user_part}{totp_badge}{cat_badge}"

            item = QListWidgetItem(label_text)
            item.setData(Qt.ItemDataRole.UserRole, secret)
            self.results_list.addItem(item)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

        # Dynamic height adjustment
        row_count = min(max(self.results_list.count(), 1), 8)
        self.results_list.setFixedHeight(row_count * 38 + 10)
        self.adjustSize()

    def _get_selected_secret(self) -> Optional[Secret]:
        current_item = self.results_list.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        if self.results_list.count() > 0:
            return self.results_list.item(0).data(Qt.ItemDataRole.UserRole)
        return None

    def show_centered(self) -> None:
        """
        Positions the palette centered horizontally in the top third of the active screen,
        clears search input, reloads records, and activates window.
        """
        self.search_input.clear()
        self.reload_records()

        # Center on active screen in top third
        screen_rect = get_active_screen_geometry()
        x = screen_rect.x() + (screen_rect.width() - self.width()) // 2
        y = screen_rect.y() + (screen_rect.height() // 5)  # top third
        self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()

    def handle_primary_action(self) -> None:
        """
        Copies password to clipboard with 30s auto-wipe and dismisses dialog.
        """
        secret = self._get_selected_secret()
        if secret and secret.password:
            SecureClipboardManager.copy(secret.password, clear_timeout_seconds=30)
            self.hide()

    def handle_copy_username(self) -> None:
        """
        Copies username to clipboard with 30s auto-wipe.
        """
        secret = self._get_selected_secret()
        if secret and secret.username:
            SecureClipboardManager.copy(secret.username, clear_timeout_seconds=30)

    def handle_copy_totp(self) -> None:
        """
        Generates and copies TOTP code with 30s auto-wipe.
        """
        secret = self._get_selected_secret()
        if secret and secret.totp_secret:
            res = TotpService.generate_totp(secret.totp_secret)
            if isinstance(res, dict):
                code = res.get("code")
            else:
                code = res
            if code:
                SecureClipboardManager.copy(code, clear_timeout_seconds=30)


    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.handle_primary_action()
            event.accept()
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_C:
                self.handle_copy_username()
                event.accept()
                return
            elif key == Qt.Key.Key_T:
                self.handle_copy_totp()
                event.accept()
                return
            elif key == Qt.Key.Key_O:
                secret = self._get_selected_secret()
                if secret:
                    self.open_full_window_requested.emit(secret.name)
                    self.hide()
                event.accept()
                return

        if key == Qt.Key.Key_Down:
            curr = self.results_list.currentRow()
            if curr < self.results_list.count() - 1:
                self.results_list.setCurrentRow(curr + 1)
            event.accept()
            return

        if key == Qt.Key.Key_Up:
            curr = self.results_list.currentRow()
            if curr > 0:
                self.results_list.setCurrentRow(curr - 1)
            event.accept()
            return

        super().keyPressEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        """
        Auto-dismiss on loss of window activation focus.
        """
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                self.hide()
        super().changeEvent(event)
