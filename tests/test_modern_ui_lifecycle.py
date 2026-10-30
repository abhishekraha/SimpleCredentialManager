import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

try:
    from PySide6 import QtCore, QtWidgets
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDialog
    HAS_QT = True
except ImportError:
    HAS_QT = False

from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.model.Secret import Secret


@unittest.skipUnless(HAS_QT, "PySide6 not installed")
class ModernUiLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "vault.scmdb"
        self.metadata_path = self.temp_path / "metadata.json"
        self.secret_path = self.temp_path / "vault.secret"

        self.service_patcher1 = patch(
            "dev.abhishekraha.secretmanager.core.SecretManagerService.VAULT_DB_FILE",
            self.db_path,
        )
        self.service_patcher2 = patch(
            "dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_MANAGER_META_DATA",
            self.metadata_path,
        )
        self.service_patcher3 = patch(
            "dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_FILE",
            self.secret_path,
        )
        self.service_patcher1.start()
        self.service_patcher2.start()
        self.service_patcher3.start()

        self.service = SecretManagerService(client_name="TestModernUI")
        self.service.setup_master_password("TestMasterPass123!", "TestMasterPass123!")
        self.service.authenticate("TestMasterPass123!")

        # Add a sample secret
        self.service.add_secret(
            name="Github",
            username="testuser",
            password="SecretPassword456!",
            url="https://github.com",
            comments="My dev account",
        )

    def tearDown(self):
        self.service_patcher1.stop()
        self.service_patcher2.stop()
        self.service_patcher3.stop()
        self.temp_dir.cleanup()

    def test_modern_main_window_loads_and_displays_secrets(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            self.assertEqual(window.secret_list.count(), 1)
            item = window.secret_list.item(0)
            self.assertIn("Github", item.text())
            self.assertIn("testuser", item.text())

            # Check detail panel
            self.assertEqual(window.detail_title.text(), "Github")
            self.assertEqual(window.username_val.text(), "testuser")
            self.assertEqual(window.password_val.text(), "••••••••••••")

            # Toggle show password
            window._toggle_show_password()
            self.assertEqual(window.password_val.text(), "SecretPassword456!")
            window._toggle_show_password()
            self.assertEqual(window.password_val.text(), "••••••••••••")
        finally:
            window.close()

    def test_lock_vault_clears_secrets_and_prompts_reauth(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            self.assertTrue(self.service.is_unlocked())
            self.assertEqual(window.secret_list.count(), 1)

            # Mock _prompt_unlock_inline to verify it gets invoked and secrets are cleared
            with patch.object(window, "_prompt_unlock_inline") as mock_prompt:
                window._lock_vault()

                # Verify vault is locked
                self.assertFalse(self.service.is_unlocked())
                self.assertIsNone(window.current_secret)
                self.assertEqual(window.secret_list.count(), 0)
                mock_prompt.assert_called_once()
        finally:
            window.close()

    def test_prompt_unlock_inline_success_restores_vault(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            # First lock the vault
            self.service.lock_vault()
            self.assertFalse(self.service.is_unlocked())

            # Mock ModernAuthDialog to simulate successful authentication
            with patch("dev.abhishekraha.secretmanager.ui.ModernMainWindow.ModernAuthDialog") as MockDialog:
                mock_dialog_inst = MagicMock()
                mock_dialog_inst.exec.return_value = QDialog.Accepted
                mock_dialog_inst.authenticated = True
                MockDialog.return_value = mock_dialog_inst

                # Authenticate service
                self.service.authenticate("TestMasterPass123!")

                window._prompt_unlock_inline()

                self.assertTrue(self.service.is_unlocked())
                self.assertEqual(window.secret_list.count(), 1)
                self.assertEqual(window.detail_title.text(), "Github")
        finally:
            window.close()

    def test_ui_switch_argument_filtering(self):
        """Test that subprocess arguments are properly sanitized without stale UI flags."""
        args_with_tkinter = ["script.py", "--tkinter", "--verbose"]
        filtered = [arg for arg in args_with_tkinter[1:] if arg not in ("--classic", "--tkinter", "--modern")]
        self.assertEqual(filtered, ["--verbose"])

        args_with_modern = ["script.py", "--modern"]
        filtered2 = [arg for arg in args_with_modern[1:] if arg not in ("--classic", "--tkinter", "--modern")]
        self.assertEqual(filtered2, [])

    def test_open_new_secret_dialog_and_add(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            with patch.object(window.service, "add_secret", wraps=window.service.add_secret) as spy_add:
                with patch("dev.abhishekraha.secretmanager.ui.SecretEditorQtDialog.SecretEditorQtDialog") as MockEditor:
                    mock_inst = MagicMock()
                    mock_inst.exec.return_value = QDialog.Accepted
                    mock_inst.secret_data = {
                        "name": "GitLab",
                        "username": "gitlabuser",
                        "password": "SecretPassGitLab!",
                        "url": "https://gitlab.com",
                        "comments": "Gitlab note",
                        "category": "login",
                        "favorite": True,
                        "totp_secret": "JBSWY3DPEHPK3PXP",
                        "tags": ["work", "dev"],
                    }
                    MockEditor.return_value = mock_inst

                    window._open_new_secret_dialog()

                    spy_add.assert_called_once_with(
                        name="GitLab",
                        username="gitlabuser",
                        password="SecretPassGitLab!",
                        url="https://gitlab.com",
                        comments="Gitlab note",
                        category="login",
                        is_favorite=True,
                        totp_secret="JBSWY3DPEHPK3PXP",
                        tags=["work", "dev"],
                    )
                    added = self.service.get_secret("GitLab")
                    self.assertIsNotNone(added)
                    self.assertEqual(added.get_username(), "gitlabuser")
                    self.assertTrue(added.is_favorite())
                    self.assertEqual(added.get_totp_secret(), "JBSWY3DPEHPK3PXP")
                    self.assertEqual(added.get_tags(), ["work", "dev"])
        finally:
            window.close()

    def test_toggle_favorite_persists_via_service(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            sec = self.service.get_secret("Github")
            self.assertFalse(sec.is_favorite())

            window.current_secret = sec
            window._toggle_favorite()

            updated = self.service.get_secret("Github")
            self.assertTrue(updated.is_favorite())
            self.assertEqual(window.fav_btn.text(), "★")

            window._toggle_favorite()
            updated2 = self.service.get_secret("Github")
            self.assertFalse(updated2.is_favorite())
            self.assertEqual(window.fav_btn.text(), "☆")
        finally:
            window.close()

    def test_display_secret_handles_iso_string_datetime(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            string_date_secret = Secret(
                name="LegacyDateSecret",
                username="legacyuser",
                password="Password123!",
                create_date="2026-10-30T10:15:30",
            )
            # Should not raise AttributeError: 'str' object has no attribute 'strftime'
            window._display_secret(string_date_secret)
            self.assertIn("2026-10-30 10:15", window.meta_footer.text())
        finally:
            window.close()

    def test_run_vault_audit(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow

        window = ModernMainWindow(service=self.service)
        try:
            window._run_vault_audit(async_worker=False)
            self.assertTrue(window.health_bar.value() > 0)
            self.assertIn("Vault Summary", window.audit_report_text.toPlainText())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
