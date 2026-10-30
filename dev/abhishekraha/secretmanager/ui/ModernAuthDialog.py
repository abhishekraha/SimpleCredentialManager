"""
PySide6 Master Password Authentication & Setup Dialog for Modern UI.
Handles initial vault setup, unlocking, lockout tracking, and vault wipe options.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QMessageBox,
        QFrame,
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QDialog = object

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import APP_NAME, APP_VERSION
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.ui.Themes import DARK_THEME_QSS


class ModernAuthDialog(QDialog):
    """
    Dialog displayed when opening Modern UI to ensure the vault is authenticated
    before the main application window is accessible.
    """

    def __init__(self, service: SecretManagerService, parent=None):
        if not HAS_QT:
            raise ImportError("PySide6 is required to instantiate ModernAuthDialog.")

        super().__init__(parent)
        self.service = service
        self.authenticated = False
        try:
            self.service.initialize()
        except Exception:
            pass
        self.is_first_time = not self.service.is_initialized()

        self.setWindowTitle(f"{APP_NAME} — {'Initial Setup' if self.is_first_time else 'Unlock Vault'}")
        self.setFixedSize(460, 360 if self.is_first_time else 320)
        self.setStyleSheet(DARK_THEME_QSS)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._refresh_lockout()

        # Timer to tick countdown if locked out
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_lockout)
        self.timer.start(1000)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        # Header Title
        title_label = QLabel(f"🔐 {APP_NAME}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #10B981;")
        layout.addWidget(title_label)

        sub_text = (
            "Create your master password to initialize your encrypted local vault."
            if self.is_first_time
            else "Enter your master password to unlock your sovereign vault."
        )
        subtitle = QLabel(sub_text)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px; margin-bottom: 6px;")
        layout.addWidget(subtitle)

        # Master Password Input
        self.pwd_input = QLineEdit(self)
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText("Enter Master Password")
        self.pwd_input.setStyleSheet("""
            QLineEdit {
                background-color: #1E222A;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px 12px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        layout.addWidget(self.pwd_input)

        if self.is_first_time:
            self.confirm_pwd_input = QLineEdit(self)
            self.confirm_pwd_input.setEchoMode(QLineEdit.Password)
            self.confirm_pwd_input.setPlaceholderText("Confirm Master Password")
            self.confirm_pwd_input.setStyleSheet("""
                QLineEdit {
                    background-color: #1E222A;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 10px 12px;
                    color: #F8FAFC;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid #10B981;
                }
            """)
            layout.addWidget(self.confirm_pwd_input)
            self.confirm_pwd_input.returnPressed.connect(self._handle_submit)

        self.pwd_input.returnPressed.connect(
            self._handle_submit if not self.is_first_time else self.confirm_pwd_input.setFocus
        )

        # Error / Status message
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #EF4444; font-size: 11px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        if not self.is_first_time:
            self.wipe_btn = QPushButton("Reset / Wipe", self)
            self.wipe_btn.setStyleSheet("""
                QPushButton {
                    background-color: #331A1E;
                    border: 1px solid #7F1D1D;
                    color: #FCA5A5;
                    padding: 9px 14px;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #7F1D1D;
                    color: #FFFFFF;
                }
            """)
            self.wipe_btn.clicked.connect(self._confirm_and_wipe)
            self.wipe_btn.setVisible(False)  # Revealed after failed attempts
            btn_layout.addWidget(self.wipe_btn)

        self.submit_btn = QPushButton("Create Vault" if self.is_first_time else "Unlock", self)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #06B6D4);
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #000000;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34D399, stop:1 #22D3EE);
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748B;
            }
        """)
        self.submit_btn.clicked.connect(self._handle_submit)
        btn_layout.addWidget(self.submit_btn)

        layout.addLayout(btn_layout)

    def _refresh_lockout(self):
        if self.is_first_time:
            return

        try:
            status = self.service.get_lockout_status()
        except Exception:
            return
        if status.get("is_locked_out"):
            rem = status.get("remaining_seconds", 0)
            self.submit_btn.setEnabled(False)
            self.pwd_input.setEnabled(False)
            self.error_label.setText(f"Too many failed attempts. Vault locked. Try again in {rem}s.")
            if hasattr(self, "wipe_btn"):
                self.wipe_btn.setVisible(True)
        else:
            self.submit_btn.setEnabled(True)
            self.pwd_input.setEnabled(True)
            if hasattr(self, "wipe_btn"):
                failed_count = status.get("failed_attempts", 0)
                if failed_count >= 3:
                    self.wipe_btn.setVisible(True)

    def _handle_submit(self):
        pwd = self.pwd_input.text()
        if not pwd:
            self.error_label.setText("Master password cannot be empty.")
            return

        if self.is_first_time:
            confirm = self.confirm_pwd_input.text()
            if pwd != confirm:
                self.error_label.setText("Passwords do not match.")
                return
            try:
                self.service.setup_master_password(pwd, confirm)
                ok, msg = self.service.authenticate(pwd)
                if ok:
                    self.authenticated = True
                    self.accept()
                else:
                    self.error_label.setText(msg or "Failed to authenticate new vault.")
            except Exception as exc:
                self.error_label.setText(str(exc))
        else:
            ok, msg = self.service.authenticate(pwd)
            if ok:
                self.authenticated = True
                self.accept()
            else:
                self.pwd_input.clear()
                self.error_label.setText(msg or "Invalid master password.")
                self._refresh_lockout()

    def _confirm_and_wipe(self):
        confirm = QMessageBox.warning(
            self,
            "Reset Vault Confirmation",
            "Are you sure you want to permanently wipe all stored credentials?\n\n"
            "This action cannot be undone. Type confirmation in the next step.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            text, ok = QtWidgets.QInputDialog.getText(
                self,
                "Type Confirmation",
                "To confirm complete vault wipe, type 'WIPE' below:",
            )
            if ok and text == "WIPE":
                self.service.reset_vault_and_wipe_all()
                QMessageBox.information(
                    self,
                    "Vault Reset",
                    "The vault has been completely wiped. Application will now restart for initial setup.",
                )
                self.reject()
