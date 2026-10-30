"""
TrayPopoverWindow: Slim, lightweight dropdown popover (320px) anchored to the system tray.
Displays live server/vault connection status, quick search, favorite credentials with live TOTP,
and one-click vault lock.
"""

from typing import Optional
from PySide6.QtCore import Qt, QPoint, QRect, QTimer, Signal, QEvent
from PySide6.QtGui import QColor, QFont, QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGraphicsDropShadowEffect,
    QFrame,
)

from dev.abhishekraha.secretmanager.core.TotpService import TotpService
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.utils.SecureClipboardManager import SecureClipboardManager


class TrayPopoverWindow(QWidget):
    """
    Compact 320px flyout anchored to the system tray icon.
    Auto-dismisses on focus loss.
    """

    open_full_window_requested = Signal()
    open_palette_requested = Signal()
    lock_vault_requested = Signal()

    def __init__(self, provider: VaultDataProvider, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.provider = provider
        self._all_secrets: list[Secret] = []

        # Frameless, on-top tool window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(320)
        self.setMaximumHeight(440)

        self._init_ui()

        # Timer for live TOTP and auto-lock countdown update
        self.totp_timer = QTimer(self)
        self.totp_timer.timeout.connect(self._refresh_live_badges)
        self.totp_timer.start(1000)

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # Card container with slate-900 styling
        self.card = QWidget(self)
        self.card.setObjectName("TrayPopoverCard")
        self.card.setStyleSheet("""
            QWidget#TrayPopoverCard {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # 1. Header (Shield + Connection Status)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        title_label = QLabel("🛡️ SCM Vault", self.card)
        title_label.setStyleSheet("color: #f8fafc; font-weight: 700; font-size: 13px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.status_dot = QLabel("●", self.card)
        self.status_dot.setStyleSheet("color: #10b981; font-size: 11px;")
        header_layout.addWidget(self.status_dot)

        self.status_text = QLabel("Local", self.card)
        self.status_text.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        header_layout.addWidget(self.status_text)

        layout.addLayout(header_layout)

        # Subtle divider
        div1 = QFrame(self.card)
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("border: none; border-top: 1px solid #1e293b;")
        layout.addWidget(div1)

        # 2. Quick Search Box
        self.search_box = QLineEdit(self.card)
        self.search_box.setPlaceholderText("Filter favorites or search...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                color: #f8fafc;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        self.search_box.textChanged.connect(self._filter_secrets)
        layout.addWidget(self.search_box)

        # 3. Favorites / Quick List
        section_label = QLabel("QUICK ACCESS", self.card)
        section_label.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; margin-top: 4px;")
        layout.addWidget(section_label)

        self.list_widget = QListWidget(self.card)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                color: #f8fafc;
            }
            QListWidget::item {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 8px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: #273549;
                border-color: #475569;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        # Subtle divider
        div2 = QFrame(self.card)
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("border: none; border-top: 1px solid #1e293b;")
        layout.addWidget(div2)

        # 4. Footer Actions
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_lock = QPushButton("🔒 Lock", self.card)
        self.btn_lock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lock.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                color: #f43f5e;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(244, 63, 94, 0.15);
                border-color: #f43f5e;
            }
        """)
        self.btn_lock.clicked.connect(self._on_lock_clicked)
        footer_layout.addWidget(self.btn_lock)

        footer_layout.addStretch()

        self.btn_search = QPushButton("⚡ Palette", self.card)
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                color: #38bdf8;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.15);
                border-color: #38bdf8;
            }
        """)
        self.btn_search.clicked.connect(self._on_palette_clicked)
        footer_layout.addWidget(self.btn_search)

        self.btn_manager = QPushButton("Workstation ↗", self.card)
        self.btn_manager.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manager.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #475569;
                color: #f8fafc;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #273549;
                border-color: #38bdf8;
            }
        """)
        self.btn_manager.clicked.connect(self._on_manager_clicked)
        footer_layout.addWidget(self.btn_manager)

        layout.addLayout(footer_layout)
        outer_layout.addWidget(self.card)

    def set_provider(self, provider: VaultDataProvider) -> None:
        """Dynamically rebinds data provider."""
        self.provider = provider
        self.reload_data()

    def reload_data(self) -> None:
        """Refreshes status header and secrets list."""
        if not self.provider:
            self._all_secrets = []
            return

        is_remote = "Remote" in type(self.provider).__name__
        if is_remote:
            client = getattr(self.provider, "client", None)
            url = getattr(client, "server_url", "remote") if client else "remote"
            self.status_text.setText("Remote")
            self.status_dot.setStyleSheet("color: #38bdf8; font-size: 11px;")
            self.status_text.setToolTip(f"Connected: {url}")
        else:
            self.status_text.setText("Local")
            self.status_dot.setStyleSheet("color: #10b981; font-size: 11px;")
            self.status_text.setToolTip("Local SQLite WAL Database")

        if self.provider.is_unlocked():
            try:
                self._all_secrets = self.provider.get_secret_records()
            except Exception:
                self._all_secrets = []
        else:
            self._all_secrets = []

        self._filter_secrets(self.search_box.text())

    def _filter_secrets(self, query: str = "") -> None:
        q = query.strip().lower()
        self.list_widget.clear()

        # Prioritize favorites, then alphabetized
        favorites = [s for s in self._all_secrets if getattr(s, "favorite", False) or getattr(s, "is_favorite", False)]
        others = [s for s in self._all_secrets if s not in favorites]
        display_pool = favorites + others

        count = 0
        for secret in display_pool:
            name = secret.get_name() if hasattr(secret, "get_name") else getattr(secret, "name", "")
            username = secret.get_username() if hasattr(secret, "get_username") else getattr(secret, "username", "")
            if q and (q not in name.lower() and q not in username.lower()):
                continue

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)

            # Build label text with live TOTP if present
            totp_code = ""
            totp_sec = secret.get_totp_secret() if hasattr(secret, "get_totp_secret") else getattr(secret, "totp_secret", None)
            if totp_sec:
                try:
                    totp_code = f" [2FA: {TotpService.generate_totp(totp_sec)}]"
                except Exception:
                    totp_code = " [2FA]"

            display_text = f"{name}"
            if username:
                display_text += f" ({username})"
            if totp_code:
                display_text += totp_code

            item.setText(display_text)
            self.list_widget.addItem(item)
            count += 1
            if count >= 8 and not q:
                break

        if count == 0:
            empty_item = QListWidgetItem("No matching credentials")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_widget.addItem(empty_item)

    def _refresh_live_badges(self) -> None:
        """Updates TOTP codes in-place every second without resetting selection."""
        if not self.isVisible() or not self.provider.is_unlocked():
            return
        # Refresh current list text
        current_row = self.list_widget.currentRow()
        self._filter_secrets(self.search_box.text())
        if current_row >= 0 and current_row < self.list_widget.count():
            self.list_widget.setCurrentRow(current_row)

    def _ensure_unlocked(self) -> bool:
        """Prompts for authentication if vault is currently locked."""
        if self.provider and self.provider.is_unlocked():
            return True

        from dev.abhishekraha.secretmanager.ui.ModernAuthDialog import ModernAuthDialog
        auth_dialog = ModernAuthDialog(service=self.provider, parent=self)
        if auth_dialog.exec() == QDialog.DialogCode.Accepted and auth_dialog.authenticated:
            return True
        return False

    def show_anchored(self, tray_rect: Optional[QRect] = None) -> None:
        """
        Positions the popover nicely above/below the tray icon or near cursor.
        Prompts for unlock if locked.
        """
        if not self._ensure_unlocked():
            self.hide()
            return

        self.reload_data()
        self.search_box.clear()

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        # Compute position: bottom-right taskbar or top-right menu bar
        if tray_rect and not tray_rect.isEmpty():
            x = tray_rect.center().x() - (self.width() // 2)
            if tray_rect.bottom() + self.height() > screen_geo.bottom():
                # Taskbar is at the bottom: place above
                y = tray_rect.top() - self.height() - 6
            else:
                # Taskbar/menu bar is at top: place below
                y = tray_rect.bottom() + 6
        else:
            # Fallback to cursor position
            cursor_pos = QCursor.pos()
            x = cursor_pos.x() - (self.width() // 2)
            y = cursor_pos.y() - self.height() - 10 if cursor_pos.y() > screen_geo.center().y() else cursor_pos.y() + 10

        # Boundary checks
        x = max(screen_geo.left() + 10, min(x, screen_geo.right() - self.width() - 10))
        y = max(screen_geo.top() + 10, min(y, screen_geo.bottom() - self.height() - 10))

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_box.setFocus()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        secret_name = item.data(Qt.ItemDataRole.UserRole)
        if not secret_name:
            return
        secret = self.provider.get_secret(secret_name)
        if secret:
            pwd = secret.get_password() if hasattr(secret, "get_password") else getattr(secret, "password", "")
            SecureClipboardManager.copy(pwd, clear_timeout_seconds=30)
            self.hide()

    def _on_lock_clicked(self) -> None:
        self.hide()
        self.lock_vault_requested.emit()

    def _on_palette_clicked(self) -> None:
        self.hide()
        self.open_palette_requested.emit()

    def _on_manager_clicked(self) -> None:
        self.hide()
        self.open_full_window_requested.emit()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                self.hide()
        super().changeEvent(event)
