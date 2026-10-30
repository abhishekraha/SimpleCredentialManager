import time
import unittest
from unittest.mock import MagicMock, patch

from dev.abhishekraha.secretmanager.utils.SecureClipboardManager import (
    SecureClipboardManager,
    _calculate_hash,
    clear_system_clipboard,
    get_current_clipboard_text,
)


class SecureClipboardManagerTests(unittest.TestCase):
    def tearDown(self):
        SecureClipboardManager.cancel_active_timer()

    def test_calculate_hash(self):
        self.assertIsNone(_calculate_hash(None))
        h = _calculate_hash("secret123")
        self.assertEqual(len(h), 64)

    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager._set_windows_clipboard_with_privacy", return_value=True)
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.platform.system", return_value="Windows")
    def test_copy_uses_windows_privacy_when_available(self, mock_system, mock_win_privacy):
        success = SecureClipboardManager.copy("test-content", clear_timeout_seconds=0)
        self.assertTrue(success)
        mock_win_privacy.assert_called_once_with("test-content")

    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager._set_windows_clipboard_with_privacy", side_effect=Exception("win32 error"))
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.SecureClipboardManager._fallback_copy", return_value=True)
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.platform.system", return_value="Windows")
    def test_copy_falls_back_when_privacy_fails(self, mock_system, mock_fallback, mock_win_privacy):
        success = SecureClipboardManager.copy("fallback-content", clear_timeout_seconds=0)
        self.assertTrue(success)
        mock_fallback.assert_called_once_with("fallback-content")

    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager._set_macos_clipboard_with_privacy", return_value=True)
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.platform.system", return_value="Darwin")
    def test_copy_uses_macos_privacy(self, mock_system, mock_mac_privacy):
        success = SecureClipboardManager.copy("mac-content", clear_timeout_seconds=0)
        self.assertTrue(success)
        mock_mac_privacy.assert_called_once_with("mac-content")

    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager._set_linux_clipboard_with_privacy", return_value=True)
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.platform.system", return_value="Linux")
    def test_copy_uses_linux_privacy(self, mock_system, mock_linux_privacy):
        success = SecureClipboardManager.copy("linux-content", clear_timeout_seconds=0)
        self.assertTrue(success)
        mock_linux_privacy.assert_called_once_with("linux-content")

    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.clear_system_clipboard")
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.get_current_clipboard_text", return_value="timed-secret")
    def test_timed_auto_clear_clears_matching_hash(self, mock_get_text, mock_clear_clipboard):
        with patch.object(SecureClipboardManager, "_fallback_copy", return_value=True):
            success = SecureClipboardManager.copy("timed-secret", clear_timeout_seconds=0.1, enable_privacy=False)
            self.assertTrue(success)
            time.sleep(0.2)
            mock_clear_clipboard.assert_called_once()

    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.clear_system_clipboard")
    @patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.get_current_clipboard_text", return_value="new_user_copied_content")
    def test_timed_auto_clear_preserves_subsequent_user_copies(self, mock_get_text, mock_clear_clipboard):
        with patch.object(SecureClipboardManager, "_fallback_copy", return_value=True):
            success = SecureClipboardManager.copy("original-secret", clear_timeout_seconds=0.1, enable_privacy=False)
            self.assertTrue(success)
            time.sleep(0.2)
            # Clipboard had different content, so clear_system_clipboard should not be called
            mock_clear_clipboard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
