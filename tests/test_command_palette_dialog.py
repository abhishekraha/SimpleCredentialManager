import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from dev.abhishekraha.secretmanager.model.Secret import Secret

app = QApplication.instance() or QApplication([])


class TestCommandPaletteDialog(unittest.TestCase):
    def setUp(self):
        from dev.abhishekraha.secretmanager.ui.CommandPaletteDialog import CommandPaletteDialog
        self.mock_provider = MagicMock()
        self.mock_provider.is_unlocked.return_value = True
        self.mock_provider.get_secret_records.return_value = [
            Secret(name="AWS Console", username="admin", password="aws_password_123", totp_secret="JBSWY3DPEHPK3PXP", category="cloud"),
            Secret(name="GitHub", username="octocat", password="gh_password_456", category="dev"),
            Secret(name="Google", username="user@gmail.com", password="goog_pwd_789", category="login"),
        ]
        self.dialog = CommandPaletteDialog(provider=self.mock_provider)

    def test_search_filters_results(self):
        self.dialog.search_input.setText("git")
        self.assertEqual(self.dialog.results_list.count(), 1)
        item = self.dialog.results_list.item(0)
        self.assertIn("GitHub", item.text())
        self.assertIn("octocat", item.text())

    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.SecureClipboardManager.copy")
    def test_enter_copies_password_and_hides(self, mock_copy):
        self.dialog.show()
        self.dialog.search_input.setText("aws")
        self.dialog.handle_primary_action()  # Simulates Enter
        mock_copy.assert_called_once_with("aws_password_123", clear_timeout_seconds=30)
        self.assertFalse(self.dialog.isVisible())

    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.SecureClipboardManager.copy")
    def test_ctrl_c_copies_username(self, mock_copy):
        self.dialog.search_input.setText("aws")
        self.dialog.handle_copy_username()
        mock_copy.assert_called_once_with("admin", clear_timeout_seconds=30)

    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.TotpService.generate_totp")
    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.SecureClipboardManager.copy")
    def test_ctrl_t_generates_and_copies_totp(self, mock_copy, mock_totp):
        mock_totp.return_value = "123456"
        self.dialog.search_input.setText("aws")
        self.dialog.handle_copy_totp()
        mock_totp.assert_called_once_with("JBSWY3DPEHPK3PXP")
        mock_copy.assert_called_once_with("123456", clear_timeout_seconds=30)

    def test_ctrl_o_emits_open_full_window_requested(self):
        self.dialog.show()
        emitted_signals = []
        self.dialog.open_full_window_requested.connect(lambda name: emitted_signals.append(name))

        self.dialog.search_input.setText("github")
        # trigger Ctrl+O
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_O, Qt.KeyboardModifier.ControlModifier)
        self.dialog.keyPressEvent(event)

        self.assertEqual(emitted_signals, ["GitHub"])
        self.assertFalse(self.dialog.isVisible())

    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.get_active_screen_geometry")
    def test_show_centered_placement(self, mock_geom):
        mock_geom.return_value = QRect(100, 100, 1200, 900)
        self.dialog.search_input.setText("some filter")
        self.dialog.show_centered()

        self.assertTrue(self.dialog.isVisible())
        self.assertEqual(self.dialog.search_input.text(), "")
        # Horizontal center: 100 + (1200 - width) // 2
        expected_x = 100 + (1200 - self.dialog.width()) // 2
        # Top third: 100 + (900 // 6) or roughly 100 + 900//4.. let's check placement
        self.assertEqual(self.dialog.x(), expected_x)
        self.dialog.hide()

    def test_set_provider_swaps_backend(self):
        new_provider = MagicMock()
        new_provider.is_unlocked.return_value = True
        new_provider.get_secret_records.return_value = [
            Secret(name="Remote AWS", username="cloud_user", password="secret_remote_pwd")
        ]
        self.dialog.set_provider(new_provider)
        self.assertEqual(self.dialog.provider, new_provider)
        self.assertEqual(self.dialog.results_list.count(), 1)
        self.assertIn("Remote AWS", self.dialog.results_list.item(0).text())


if __name__ == "__main__":
    unittest.main()
