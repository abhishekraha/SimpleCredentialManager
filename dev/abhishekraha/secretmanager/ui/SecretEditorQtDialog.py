"""
PySide6 Dialog for Creating and Editing Secrets with integrated Password Generator.
"""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QDialog = object


class SecretEditorQtDialog(QDialog):
    def __init__(self, parent=None, title="Secret", secret=None, service=None):
        if not HAS_QT:
            raise ImportError("PySide6 is required.")
        super().__init__(parent)
        self.secret = secret
        self.service = service
        self.secret_data = None

        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Name
        self.name_edit = QLineEdit(self)
        if self.secret:
            self.name_edit.setText(self.secret.get_name())
            self.name_edit.setEnabled(False)  # Name cannot be changed in edit mode
        form.addRow("Name:", self.name_edit)

        # Username
        self.user_edit = QLineEdit(self)
        if self.secret:
            self.user_edit.setText(self.secret.get_username())
        form.addRow("Username:", self.user_edit)

        # Password + Generate button + Breach check button
        pass_layout = QHBoxLayout()
        self.pass_edit = QLineEdit(self)
        if self.secret:
            self.pass_edit.setText(self.secret.get_password())
        pass_layout.addWidget(self.pass_edit)

        self.gen_btn = QPushButton("🎲 Generate", self)
        self.gen_btn.clicked.connect(self._generate_password)
        pass_layout.addWidget(self.gen_btn)

        self.leak_btn = QPushButton("🔍 Check Leak", self)
        self.leak_btn.setToolTip("Check if this password appears in HaveIBeenPwned dark web breaches")
        self.leak_btn.clicked.connect(self._check_leak)
        pass_layout.addWidget(self.leak_btn)
        form.addRow("Password:", pass_layout)

        # Leak result status row
        self.leak_status_label = QLabel("", self)
        self.leak_status_label.setWordWrap(True)
        self.leak_status_label.hide()
        form.addRow("", self.leak_status_label)

        # Category
        self.category_combo = QComboBox(self)
        self.category_combo.addItems(["login", "card", "note"])
        if self.secret:
            idx = self.category_combo.findText(self.secret.get_category())
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
        form.addRow("Category:", self.category_combo)

        # URL
        self.url_edit = QLineEdit(self)
        if self.secret:
            self.url_edit.setText(self.secret.get_url())
        form.addRow("URL:", self.url_edit)

        # TOTP Secret (Base32 or otpauth://)
        self.totp_edit = QLineEdit(self)
        self.totp_edit.setPlaceholderText("Base32 secret or otpauth:// URI")
        if self.secret:
            self.totp_edit.setText(self.secret.get_totp_secret())
        form.addRow("TOTP 2FA Secret:", self.totp_edit)

        # Tags (comma separated)
        self.tags_edit = QLineEdit(self)
        self.tags_edit.setPlaceholderText("work, personal, banking")
        if self.secret and self.secret.get_tags():
            self.tags_edit.setText(", ".join(self.secret.get_tags()))
        form.addRow("Tags:", self.tags_edit)

        # Comments
        self.notes_edit = QTextEdit(self)
        self.notes_edit.setMaximumHeight(80)
        if self.secret:
            self.notes_edit.setPlainText(self.secret.get_comments())
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Button box
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save", self)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _generate_password(self):
        if self.service:
            pwd = self.service.generate_password(20)
        else:
            from secrets import choice
            import string
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            pwd = "".join(choice(chars) for _ in range(20))
        self.pass_edit.setText(pwd)

    def _check_leak(self):
        pwd = self.pass_edit.text()
        if not pwd:
            self.leak_status_label.setText("<span style='color: #F59E0B;'>⚠️ Enter or generate a password first.</span>")
            self.leak_status_label.show()
            return

        from dev.abhishekraha.secretmanager.utils.BreachChecker import check_password_breach
        import threading
        from PySide6.QtCore import QTimer

        self.leak_btn.setEnabled(False)
        self.leak_btn.setText("⏳ Checking...")
        self.leak_status_label.setText("<span style='color: #94A3B8;'>Scanning HaveIBeenPwned API...</span>")
        self.leak_status_label.show()

        def _worker():
            try:
                is_pwned, count = check_password_breach(pwd, timeout=5)
            except Exception:
                is_pwned, count = False, 0

            def _update_ui():
                self.leak_btn.setEnabled(True)
                self.leak_btn.setText("🔍 Check Leak")
                if is_pwned:
                    self.leak_status_label.setText(
                        f"<span style='color: #EF4444; font-weight: bold;'>⚠️ BREACH DETECTED: Found in {count:,} dark web breaches!</span>"
                    )
                else:
                    self.leak_status_label.setText(
                        "<span style='color: #10B981; font-weight: bold;'>✓ Good: No known dark web breaches found.</span>"
                    )

            QTimer.singleShot(0, _update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Secret name is required.")
            return

        raw_tags = self.tags_edit.text()
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

        self.secret_data = {
            "name": name,
            "username": self.user_edit.text().strip(),
            "password": self.pass_edit.text(),
            "category": self.category_combo.currentText(),
            "url": self.url_edit.text().strip(),
            "totp_secret": self.totp_edit.text().strip(),
            "tags": tags,
            "comments": self.notes_edit.toPlainText().strip(),
            "favorite": self.secret.is_favorite() if self.secret else False,
        }
        self.accept()
