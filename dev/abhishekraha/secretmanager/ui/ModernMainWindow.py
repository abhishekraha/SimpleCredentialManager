"""
Modern 3-Pane Main Application Window implemented in PySide6.
Pane 1: Sidebar with navigation (All, Favorites, Categories, Tags, Security Health)
Pane 2: Item List with live search filter and metadata badges
Pane 3: Detail panel with click-to-copy, password generator, and TOTP circular countdown arc
"""

import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path when invoked directly
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QAction, QColor, QFont, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QSplitter,
        QStackedWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QMainWindow = object
    QDialog = object

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import SESSION_IDLE_LOCK_SECONDS
from dev.abhishekraha.secretmanager.core.PasswordHealthService import PasswordHealthService
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.core.TotpService import TotpService
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.ui.ModernAuthDialog import ModernAuthDialog
from dev.abhishekraha.secretmanager.ui.Themes import DARK_THEME_QSS, LIGHT_THEME_QSS
from dev.abhishekraha.secretmanager.ui.TotpCountdownWidget import TotpCountdownWidget
from dev.abhishekraha.secretmanager.utils.BreachChecker import check_password_breach
from dev.abhishekraha.secretmanager.utils.SecureClipboardManager import SecureClipboardManager


class ModernMainWindow(QMainWindow):
    """
    PySide6 Modern 3-Pane Application Window for Simple Credential Manager.
    """

    def __init__(self, service=None, parent=None):
        if not HAS_QT:
            raise ImportError("PySide6 is required to instantiate ModernMainWindow.")

        super().__init__(parent)
        self.service = service or SecretManagerService(client_name="Modern-UI")
        self.is_dark_mode = True
        self.current_filter = "all"
        self.current_secret = None
        self._last_activity_time = datetime.now()

        self.setWindowTitle("Simple Credential Manager")
        self.resize(1100, 700)
        self.setMinimumSize(850, 550)

        self._init_ui()
        self._apply_theme()
        self._init_timer()
        if not self.service.is_unlocked():
            self._prompt_unlock_inline()
        else:
            self.refresh_vault()

    def _init_ui(self):
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 3-Pane Splitter
        self.splitter = QSplitter(Qt.Horizontal, self.central_widget)

        # 1. Sidebar Frame
        self.sidebar_frame = self._build_sidebar()
        self.splitter.addWidget(self.sidebar_frame)

        # 2. Item List Frame
        self.item_list_frame = self._build_item_list()
        self.splitter.addWidget(self.item_list_frame)

        # 3. Detail Frame
        self.detail_frame = self._build_detail_panel()
        self.splitter.addWidget(self.detail_frame)

        # Configure splitter proportions: 200px, 320px, 580px
        self.splitter.setSizes([200, 320, 580])
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, False)

        main_layout.addWidget(self.splitter)

    # ------------------ PANE 1: SIDEBAR ------------------
    def _build_sidebar(self):
        frame = QFrame(self)
        frame.setObjectName("SidebarFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(10)

        # App Brand Header
        brand_label = QLabel("🔐 SCM Vault", frame)
        brand_font = QFont()
        brand_font.setBold(True)
        brand_font.setPixelSize(16)
        brand_label.setFont(brand_font)
        layout.addWidget(brand_label)

        # Navigation List
        self.nav_list = QListWidget(frame)
        self.nav_list.setObjectName("NavList")

        nav_items = [
            ("📁 All Items", "all"),
            ("⭐ Favorites", "favorites"),
            ("🔑 Logins", "cat_login"),
            ("💳 Cards", "cat_card"),
            ("📝 Secure Notes", "cat_note"),
            ("🛡️ Health Audit", "health"),
        ]

        for text, key in nav_items:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)

        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)

        layout.addStretch()

        # Theme toggle button
        self.theme_btn = QPushButton("🌓 Toggle Theme", frame)
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        # Switch to Classic UI button
        self.switch_ui_btn = QPushButton("🖥️ Switch to Classic UI", frame)
        self.switch_ui_btn.clicked.connect(self._switch_to_classic_ui)
        layout.addWidget(self.switch_ui_btn)

        # Lock Vault button
        self.lock_btn = QPushButton("🔒 Lock Vault", frame)
        self.lock_btn.setObjectName("DangerButton")
        self.lock_btn.clicked.connect(self._lock_vault)
        layout.addWidget(self.lock_btn)

        return frame

    # ------------------ PANE 2: ITEM LIST ------------------
    def _build_item_list(self):
        frame = QFrame(self)
        frame.setObjectName("ItemListFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(10)

        # Search box
        self.search_input = QLineEdit(frame)
        self.search_input.setObjectName("SearchBox")
        self.search_input.setPlaceholderText("🔍 Search vault...")
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # Toolbar above items
        toolbar_layout = QHBoxLayout()
        self.items_count_label = QLabel("0 items", frame)
        self.items_count_label.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        toolbar_layout.addWidget(self.items_count_label)
        toolbar_layout.addStretch()

        self.add_btn = QPushButton("+ New", frame)
        self.add_btn.setObjectName("PrimaryButton")
        self.add_btn.clicked.connect(self._open_new_secret_dialog)
        toolbar_layout.addWidget(self.add_btn)
        layout.addLayout(toolbar_layout)

        # Secret List Widget
        self.secret_list = QListWidget(frame)
        self.secret_list.setObjectName("SecretListWidget")
        self.secret_list.currentRowChanged.connect(self._on_secret_selected)
        layout.addWidget(self.secret_list)

        return frame

    # ------------------ PANE 3: DETAIL PANEL ------------------
    def _build_detail_panel(self):
        frame = QFrame(self)
        frame.setObjectName("DetailFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Stacked widget to switch between Secret View and Health Audit View
        self.detail_stack = QStackedWidget(frame)

        # View 1: Secret Detail View
        self.secret_view_widget = QWidget()
        self._setup_secret_view(self.secret_view_widget)
        self.detail_stack.addWidget(self.secret_view_widget)

        # View 2: Health Audit View
        self.health_view_widget = QWidget()
        self._setup_health_view(self.health_view_widget)
        self.detail_stack.addWidget(self.health_view_widget)

        # View 3: Empty Placeholder
        self.empty_view_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_view_widget)
        empty_label = QLabel("Select an item from the list to view details", self.empty_view_widget)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: #64748B; font-size: 14px;")
        empty_layout.addWidget(empty_label)
        self.detail_stack.addWidget(self.empty_view_widget)

        self.detail_stack.setCurrentWidget(self.empty_view_widget)
        layout.addWidget(self.detail_stack)

        return frame

    def _setup_secret_view(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header: Name, Favorite star, and Action buttons
        header_layout = QHBoxLayout()
        self.detail_title = QLabel("Secret Name", parent)
        self.detail_title.setObjectName("DetailTitle")
        header_layout.addWidget(self.detail_title)

        self.fav_btn = QPushButton("★", parent)
        self.fav_btn.setFixedSize(32, 32)
        self.fav_btn.setToolTip("Toggle Favorite")
        self.fav_btn.clicked.connect(self._toggle_favorite)
        header_layout.addWidget(self.fav_btn)

        header_layout.addStretch()

        self.edit_btn = QPushButton("Edit", parent)
        self.edit_btn.clicked.connect(self._open_edit_dialog)
        header_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete", parent)
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._delete_current_secret)
        header_layout.addWidget(self.delete_btn)

        layout.addLayout(header_layout)

        # Subtitle (Category & URL)
        self.detail_subtitle = QLabel("Login • https://example.com", parent)
        self.detail_subtitle.setObjectName("DetailSubtitle")
        layout.addWidget(self.detail_subtitle)

        # Credentials Group
        cred_group = QGroupBox("Credentials", parent)
        cred_layout = QVBoxLayout(cred_group)
        cred_layout.setSpacing(10)

        # Username row
        user_row = QHBoxLayout()
        user_label = QLabel("Username:", cred_group)
        user_label.setFixedWidth(80)
        user_row.addWidget(user_label)
        self.username_val = QLabel("", cred_group)
        self.username_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.username_val.setCursor(Qt.PointingHandCursor)
        self.username_val.setToolTip("Click to copy username")
        self.username_val.mousePressEvent = lambda event: self._on_field_clicked(event, self._copy_username, self.username_val)
        user_row.addWidget(self.username_val, 1)
        self.copy_user_btn = QPushButton("📋 Copy", cred_group)
        self.copy_user_btn.clicked.connect(self._copy_username)
        user_row.addWidget(self.copy_user_btn)
        cred_layout.addLayout(user_row)

        # Password row
        pass_row = QHBoxLayout()
        pass_label = QLabel("Password:", cred_group)
        pass_label.setFixedWidth(80)
        pass_row.addWidget(pass_label)
        self.password_val = QLabel("••••••••••••", cred_group)
        self.password_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.password_val.setCursor(Qt.PointingHandCursor)
        self.password_val.setToolTip("Click to copy password")
        self.password_val.mousePressEvent = lambda event: self._on_field_clicked(event, self._copy_password, self.password_val)
        pass_row.addWidget(self.password_val, 1)
        self.toggle_pass_btn = QPushButton("👁️ Show", cred_group)
        self.toggle_pass_btn.clicked.connect(self._toggle_show_password)
        pass_row.addWidget(self.toggle_pass_btn)
        self.copy_pass_btn = QPushButton("📋 Copy", cred_group)
        self.copy_pass_btn.clicked.connect(self._copy_password)
        pass_row.addWidget(self.copy_pass_btn)
        self.check_leak_btn = QPushButton("🔍 Check Leak", cred_group)
        self.check_leak_btn.setToolTip("Check if this password is compromised on the dark web via HaveIBeenPwned")
        self.check_leak_btn.clicked.connect(self._check_current_password_leak)
        pass_row.addWidget(self.check_leak_btn)
        cred_layout.addLayout(pass_row)

        # Leak result badge/status
        self.leak_status_label = QLabel("", cred_group)
        self.leak_status_label.setWordWrap(True)
        self.leak_status_label.hide()
        cred_layout.addWidget(self.leak_status_label)

        layout.addWidget(cred_group)

        # TOTP 2FA Section Group
        self.totp_group = QGroupBox("One-Time Password (TOTP 2FA)", parent)
        totp_layout = QHBoxLayout(self.totp_group)

        self.totp_arc = TotpCountdownWidget(self.totp_group, size=46)
        totp_layout.addWidget(self.totp_arc)

        self.totp_code_label = QLabel("--- ---", self.totp_group)
        self.totp_code_label.setCursor(Qt.PointingHandCursor)
        self.totp_code_label.setToolTip("Click to copy 2FA code")
        self.totp_code_label.mousePressEvent = lambda event: self._on_field_clicked(event, self._copy_totp, self.totp_code_label)
        totp_font = QFont("Monospace")
        totp_font.setBold(True)
        totp_font.setPixelSize(22)
        self.totp_code_label.setFont(totp_font)
        totp_layout.addWidget(self.totp_code_label, 1)

        self.copy_totp_btn = QPushButton("📋 Copy Code", self.totp_group)
        self.copy_totp_btn.clicked.connect(self._copy_totp)
        totp_layout.addWidget(self.copy_totp_btn)

        layout.addWidget(self.totp_group)

        # Notes / Comments
        notes_group = QGroupBox("Notes", parent)
        notes_layout = QVBoxLayout(notes_group)
        self.notes_label = QLabel("", notes_group)
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        notes_layout.addWidget(self.notes_label)
        layout.addWidget(notes_group)

        # Metadata Footer
        self.meta_footer = QLabel("", parent)
        self.meta_footer.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.meta_footer)

        layout.addStretch()

    def _setup_health_view(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = QLabel("🛡️ Vault Security Health Audit", parent)
        header.setObjectName("DetailTitle")
        layout.addWidget(header)

        # Health Score card
        score_row = QHBoxLayout()
        self.score_label = QLabel("Score: -- / 100", parent)
        score_font = QFont()
        score_font.setBold(True)
        score_font.setPixelSize(22)
        self.score_label.setFont(score_font)
        score_row.addWidget(self.score_label)

        self.run_audit_btn = QPushButton("🔄 Re-Audit Vault", parent)
        self.run_audit_btn.clicked.connect(lambda: self._run_vault_audit(check_breaches=False))
        score_row.addWidget(self.run_audit_btn)

        self.breach_audit_btn = QPushButton("🔍 Check Dark Web Breaches", parent)
        self.breach_audit_btn.setToolTip("Scan HaveIBeenPwned API for dark web leaks using k-anonymity (zero plaintext sent)")
        self.breach_audit_btn.clicked.connect(lambda: self._run_vault_audit(check_breaches=True))
        score_row.addWidget(self.breach_audit_btn)
        score_row.addStretch()
        layout.addLayout(score_row)

        self.health_bar = QProgressBar(parent)
        self.health_bar.setRange(0, 100)
        self.health_bar.setValue(0)
        layout.addWidget(self.health_bar)

        # Audit Report Details
        self.audit_report_text = QTextEdit(parent)
        self.audit_report_text.setReadOnly(True)
        layout.addWidget(self.audit_report_text, 1)

    # ------------------ TIMER & LIVE UPDATES ------------------
    def _init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)  # every 1 second

    def _on_tick(self):
        # Update TOTP widget if visible
        if self.current_secret and self.current_secret.get_totp_secret():
            try:
                totp_res = TotpService.generate_totp(self.current_secret.get_totp_secret())
                self.totp_code_label.setText(totp_res["formatted_code"])
                self.totp_arc.set_remaining(totp_res["remaining_seconds"], 30)
            except Exception:
                self.totp_code_label.setText("Invalid Secret")

        # Inactivity auto-lock check
        if self.service.is_unlocked():
            elapsed = (datetime.now() - self._last_activity_time).total_seconds()
            if elapsed >= SESSION_IDLE_LOCK_SECONDS:
                self._lock_vault()

    def _register_activity(self):
        self._last_activity_time = datetime.now()

    def mousePressEvent(self, event):
        self._register_activity()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        self._register_activity()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "timer") and self.timer:
            self.timer.stop()
        self.service.lock_vault()
        super().closeEvent(event)

    # ------------------ DATA & FILTERING ------------------
    def refresh_vault(self):
        if not self.service.is_unlocked():
            return

        all_secrets = self.service.get_secret_records()
        search_query = self.search_input.text().strip().lower()

        filtered = []
        for s in all_secrets:
            # Check nav filter
            if self.current_filter == "favorites" and not s.is_favorite():
                continue
            elif self.current_filter == "cat_login" and s.get_category() != "login":
                continue
            elif self.current_filter == "cat_card" and s.get_category() != "card":
                continue
            elif self.current_filter == "cat_note" and s.get_category() != "note":
                continue

            # Check search query
            if search_query:
                haystack = f"{s.get_name()} {s.get_username()} {s.get_url()} {s.get_comments()} {' '.join(s.get_tags())}".lower()
                if search_query not in haystack:
                    continue

            filtered.append(s)

        self.secret_list.clear()
        for s in filtered:
            fav_indicator = "★ " if s.is_favorite() else ""
            item = QListWidgetItem(f"{fav_indicator}{s.get_name()}\n{s.get_username() or 'No username'}")
            item.setData(Qt.UserRole, s.get_name())
            self.secret_list.addItem(item)

        self.items_count_label.setText(f"{len(filtered)} items")

        # Select first item if nothing selected
        if self.secret_list.count() > 0:
            self.secret_list.setCurrentRow(0)
        else:
            self.current_secret = None
            if self.current_filter != "health":
                self.detail_stack.setCurrentWidget(self.empty_view_widget)

    def _on_nav_changed(self, row):
        item = self.nav_list.item(row)
        if not item:
            return
        key = item.data(Qt.UserRole)
        self.current_filter = key

        if key == "health":
            self.detail_stack.setCurrentWidget(self.health_view_widget)
            self._run_vault_audit()
        else:
            self.refresh_vault()

    def _on_search_changed(self, text):
        self.refresh_vault()

    def _on_secret_selected(self, row):
        if row < 0 or not self.service.is_unlocked():
            return
        item = self.secret_list.item(row)
        if not item:
            return
        secret_name = item.data(Qt.UserRole)
        self.current_secret = self.service.get_secret(secret_name)
        if not self.current_secret:
            return

        self._display_secret(self.current_secret)

    def _display_secret(self, secret):
        self.detail_stack.setCurrentWidget(self.secret_view_widget)
        self.detail_title.setText(secret.get_name())
        self.fav_btn.setText("★" if secret.is_favorite() else "☆")
        self.detail_subtitle.setText(f"{secret.get_category().capitalize()} • {secret.get_url() or 'No URL'}")

        self.username_val.setText(secret.get_username() or "--")
        self.password_val.setText("••••••••••••")
        self.toggle_pass_btn.setText("👁️ Show")
        self.check_leak_btn.setEnabled(True)
        self.check_leak_btn.setText("🔍 Check Leak")
        self.leak_status_label.hide()
        self.leak_status_label.setText("")

        # TOTP visibility
        totp_secret = secret.get_totp_secret()
        if totp_secret:
            self.totp_group.show()
            self._on_tick()
        else:
            self.totp_group.hide()

        self.notes_label.setText(secret.get_comments() or "No notes.")
        create_date = secret.get_create_date()
        if hasattr(create_date, "strftime"):
            created_str = create_date.strftime("%Y-%m-%d %H:%M")
        elif create_date:
            created_str = str(create_date).replace("T", " ")[:16]
        else:
            created_str = "Unknown"
        self.meta_footer.setText(f"Created: {created_str} • Tags: {', '.join(secret.get_tags()) or 'None'}")

    # ------------------ ACTIONS ------------------
    def _toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self._apply_theme()

    def _apply_theme(self):
        qss = DARK_THEME_QSS if self.is_dark_mode else LIGHT_THEME_QSS
        self.setStyleSheet(qss)

    def _switch_to_classic_ui(self):
        self.service.set_ui_preference("classic")
        msg = QMessageBox(self)
        msg.setWindowTitle("UI Preference Changed")
        msg.setText("UI preference saved. Please restart the application to apply the new interface.")
        msg.setInformativeText("Would you like to restart immediately?")
        restart_btn = msg.addButton("Restart Now", QMessageBox.AcceptRole)
        msg.addButton("Restart Later", QMessageBox.RejectRole)
        msg.setDefaultButton(restart_btn)
        msg.exec()

        if msg.clickedButton() == restart_btn:
            if hasattr(self, "timer") and self.timer:
                self.timer.stop()
            self.service.lock_vault()
            self.close()
            # Launch classic UI process or restart executable
            import os
            import subprocess
            filtered_args = [arg for arg in sys.argv[1:] if arg not in ("--classic", "--tkinter", "--modern")]
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable] + filtered_args + ["--classic"])
            else:
                main_script = os.path.abspath(sys.argv[0])
                subprocess.Popen([sys.executable, main_script] + filtered_args + ["--classic"])
            sys.exit(0)

    def _lock_vault(self):
        """
        Locks the vault, clears session data and widget displays,
        and prompts the user to re-authenticate without terminating the app.
        """
        self.service.lock_vault()
        self.current_secret = None
        self.secret_list.clear()
        self.items_count_label.setText("0 items")
        self.detail_stack.setCurrentWidget(self.empty_view_widget)

        # Prompt for re-authentication
        self._prompt_unlock_inline()

    def _prompt_unlock_inline(self):
        """
        Shows the authentication dialog. If authenticated, loads secrets.
        If user cancels, closes the main window and exits.
        """
        auth_dialog = ModernAuthDialog(service=self.service, parent=self)
        if auth_dialog.exec() == QDialog.Accepted and auth_dialog.authenticated:
            self._last_activity_time = datetime.now()
            self.refresh_vault()
            self.show()
        else:
            # User declined to authenticate; close window
            if hasattr(self, "timer") and self.timer:
                self.timer.stop()
            self.close()
            QApplication.quit()

    def _on_field_clicked(self, event, copy_func, target_widget):
        if event.button() == Qt.LeftButton:
            copy_func()
            # Visual feedback on click
            orig_tooltip = target_widget.toolTip()
            target_widget.setToolTip("Copied!")
            QTimer.singleShot(1500, lambda: target_widget.setToolTip(orig_tooltip))

    def _copy_username(self):
        if self.current_secret:
            SecureClipboardManager.copy(self.current_secret.get_username())
            self.copy_user_btn.setText("✓ Copied")
            QTimer.singleShot(1500, lambda: self.copy_user_btn.setText("📋 Copy"))

    def _copy_password(self):
        if self.current_secret:
            SecureClipboardManager.copy(self.current_secret.get_password())
            self.copy_pass_btn.setText("✓ Copied")
            QTimer.singleShot(1500, lambda: self.copy_pass_btn.setText("📋 Copy"))

    def _copy_totp(self):
        if self.current_secret and self.current_secret.get_totp_secret():
            try:
                res = TotpService.generate_totp(self.current_secret.get_totp_secret())
                SecureClipboardManager.copy(res["code"])
                self.copy_totp_btn.setText("✓ Copied")
                QTimer.singleShot(1500, lambda: self.copy_totp_btn.setText("📋 Copy Code"))
            except Exception:
                pass

    def _check_current_password_leak(self):
        if not self.current_secret:
            return
        pwd = self.current_secret.get_password()
        if not pwd:
            self.leak_status_label.setText("<span style='color: #F59E0B;'>⚠️ Password is empty</span>")
            self.leak_status_label.show()
            return

        self.check_leak_btn.setEnabled(False)
        self.check_leak_btn.setText("⏳ Checking...")
        self.leak_status_label.setText("<span style='color: #94A3B8;'>Contacting HaveIBeenPwned API (k-anonymity)...</span>")
        self.leak_status_label.show()

        import threading

        def _worker():
            try:
                is_pwned, count = check_password_breach(pwd, timeout=5)
            except Exception:
                is_pwned, count = False, 0

            def _update_ui():
                self.check_leak_btn.setEnabled(True)
                self.check_leak_btn.setText("🔍 Check Leak")
                if is_pwned:
                    self.leak_status_label.setText(
                        f"<span style='color: #EF4444; font-weight: bold;'>⚠️ BREACH DETECTED: Leaked in {count:,} known data breaches! Change this password immediately.</span>"
                    )
                else:
                    self.leak_status_label.setText(
                        "<span style='color: #10B981; font-weight: bold;'>✓ Good news: No known dark web breaches found for this password.</span>"
                    )

            QTimer.singleShot(0, _update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_show_password(self):
        if not self.current_secret:
            return
        if self.password_val.text() == "••••••••••••":
            self.password_val.setText(self.current_secret.get_password())
            self.toggle_pass_btn.setText("🙈 Hide")
        else:
            self.password_val.setText("••••••••••••")
            self.toggle_pass_btn.setText("👁️ Show")

    def _toggle_favorite(self):
        if not self.current_secret:
            return
        new_fav = not self.current_secret.is_favorite()
        self.service.update_secret(
            original_name=self.current_secret.get_name(),
            is_favorite=new_fav,
        )
        self.current_secret = self.service.get_secret(self.current_secret.get_name())
        self.fav_btn.setText("★" if (self.current_secret and self.current_secret.is_favorite()) else "☆")
        self.refresh_vault()

    def _delete_current_secret(self):
        if not self.current_secret:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete secret '{self.current_secret.get_name()}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.service.delete_secret(self.current_secret.get_name())
            self.current_secret = None
            self.refresh_vault()

    def _open_new_secret_dialog(self):
        from dev.abhishekraha.secretmanager.ui.SecretEditorQtDialog import SecretEditorQtDialog
        dialog = SecretEditorQtDialog(self, title="New Secret", service=self.service)
        if dialog.exec() == QDialog.Accepted and dialog.secret_data:
            data = dialog.secret_data
            self.service.add_secret(
                name=data["name"],
                username=data["username"],
                password=data["password"],
                url=data["url"],
                comments=data["comments"],
                category=data.get("category", "login"),
                is_favorite=data.get("favorite", False),
                totp_secret=data.get("totp_secret", ""),
                tags=data.get("tags", []),
            )
            self.refresh_vault()

    def _open_edit_dialog(self):
        if not self.current_secret:
            return
        from dev.abhishekraha.secretmanager.ui.SecretEditorQtDialog import SecretEditorQtDialog
        dialog = SecretEditorQtDialog(self, title="Edit Secret", secret=self.current_secret, service=self.service)
        if dialog.exec() == QDialog.Accepted and dialog.secret_data:
            data = dialog.secret_data
            target_name = data.get("name") or self.current_secret.get_name()
            self.service.update_secret(
                original_name=self.current_secret.get_name(),
                new_name=target_name,
                username=data["username"],
                password=data["password"],
                url=data["url"],
                comments=data["comments"],
                category=data.get("category", "login"),
                is_favorite=data.get("favorite", False),
                totp_secret=data.get("totp_secret", ""),
                tags=data.get("tags", []),
            )
            self.current_secret = self.service.get_secret(target_name)
            self._display_secret(self.current_secret)
            self.refresh_vault()

    def _run_vault_audit(self, check_breaches=False, async_worker=True):
        secrets = self.service.get_secret_records()
        if not secrets:
            self.score_label.setText("Score: -- / 100")
            self.health_bar.setRange(0, 100)
            self.health_bar.setValue(0)
            self.audit_report_text.setPlainText("No secrets in vault to audit.")
            return

        # Disable buttons and start indeterminate animated progress bar
        self.run_audit_btn.setEnabled(False)
        self.breach_audit_btn.setEnabled(False)
        self.health_bar.setRange(0, 0)  # Qt indeterminate animated barber-pole mode
        self.score_label.setText("Score: ⏳ Auditing...")

        status_prefix = "🔍 Auditing vault with Dark Web Breach check (HaveIBeenPwned API)..." if check_breaches else "🔄 Auditing vault credentials (entropy, length, staleness, reuse)..."
        self.audit_report_text.setPlainText(
            f"{status_prefix}\n\n"
            f"[1/3] Checking entropy and complexity algorithms...\n"
            f"[2/3] Analyzing duplicate hashes and stale rotations...\n"
            + ("[3/3] Querying HaveIBeenPwned k-anonymity API in background...\n\nPlease stand by..." if check_breaches else "[3/3] Compiling health score matrix...")
        )

        if not async_worker:
            res = PasswordHealthService.audit_vault(secrets, check_breaches=check_breaches)
            self.run_audit_btn.setEnabled(True)
            self.breach_audit_btn.setEnabled(True)
            self.health_bar.setRange(0, 100)
            self._render_audit_report(res, check_breaches=check_breaches)
            return

        import threading

        def _audit_worker():
            try:
                res = PasswordHealthService.audit_vault(secrets, check_breaches=check_breaches, breach_timeout=5)
            except Exception:
                res = None

            def _update_ui():
                self.run_audit_btn.setEnabled(True)
                self.breach_audit_btn.setEnabled(True)
                self.health_bar.setRange(0, 100)
                if res:
                    self._render_audit_report(res, check_breaches=check_breaches)
                else:
                    self.score_label.setText("Score: Error")
                    self.health_bar.setValue(0)
                    self.audit_report_text.setPlainText("❌ Audit encountered an error while processing.")

            QTimer.singleShot(150, _update_ui)

        threading.Thread(target=_audit_worker, daemon=True).start()

    def _render_audit_report(self, audit_res, check_breaches=False):
        score = audit_res["health_score"]
        self.score_label.setText(f"Score: {score} / 100")
        self.health_bar.setValue(score)

        report_lines = [
            f"Vault Summary:",
            f"• Total Secrets: {audit_res['total_secrets']}",
            f"• Weak Passwords: {len(audit_res['weak_secrets'])}",
            f"• Reused Passwords: {audit_res['summary']['reused_count']}",
            f"• Stale Passwords (>365d): {len(audit_res['stale_secrets'])}",
        ]

        if check_breaches:
            breaches = audit_res.get("breached_secrets", [])
            report_lines.append(f"• Dark Web Breaches: {len(breaches)}")
            report_lines.extend(["", "=== ⚠️ DARK WEB COMPROMISED SECRETS ==="])
            if breaches:
                for b in breaches:
                    report_lines.append(f"🚨 {b['name']}: Found in {b['breach_count']:,} data breaches! Rotate immediately.")
            else:
                report_lines.append("✓ None! No passwords found in known data breaches.")

        report_lines.extend(["", "--- Weak Passwords ---"])
        for w in audit_res["weak_secrets"]:
            report_lines.append(f"• {w['name']}: {w['reason']} ({w['length']} chars, {w['entropy']} bits)")

        report_lines.extend(["", "--- Reused Passwords ---"])
        for r in audit_res["reused_secrets"]:
            report_lines.append(f"• Mask {r['password_mask']} shared across: {', '.join(r['secret_names'])}")

        report_lines.extend(["", "--- Stale Passwords ---"])
        for st in audit_res["stale_secrets"]:
            report_lines.append(f"• {st['name']}: {st['age_days']} days unrotated")

        self.audit_report_text.setPlainText("\n".join(report_lines))
