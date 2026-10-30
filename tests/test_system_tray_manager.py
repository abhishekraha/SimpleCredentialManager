import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from dev.abhishekraha.secretmanager.ui.SystemTrayManager import SystemTrayManager

app = QApplication.instance() or QApplication([])


class TestSystemTrayManager(unittest.TestCase):
    def setUp(self):
        self.mock_provider = MagicMock()
        self.mock_palette = MagicMock()
        self.mock_main_window = MagicMock()
        self.tray = SystemTrayManager(
            provider=self.mock_provider,
            palette_dialog=self.mock_palette,
            main_window=self.mock_main_window,
        )

    def tearDown(self):
        if hasattr(self.tray, "tray_icon") and self.tray.tray_icon:
            self.tray.tray_icon.hide()

    def test_tray_initialization(self):
        self.assertIsNotNone(self.tray.tray_icon)
        self.assertFalse(QApplication.quitOnLastWindowClosed())
        self.assertEqual(self.tray.provider, self.mock_provider)
        self.assertEqual(self.tray.palette_dialog, self.mock_palette)
        self.assertEqual(self.tray.main_window, self.mock_main_window)
        # Check context menu actions exist
        actions = self.tray.context_menu.actions()
        action_texts = [a.text() for a in actions]
        self.assertTrue(any("Quick Search" in t for t in action_texts))
        self.assertTrue(any("Open Vault Manager" in t for t in action_texts))
        self.assertTrue(any("Lock Vault Now" in t for t in action_texts))
        self.assertTrue(any("Switch Backend" in t for t in action_texts))
        self.assertTrue(any("Quit SCM" in t for t in action_texts))

    def test_switch_backend_locks_and_swaps_provider(self):
        new_provider = MagicMock()
        self.tray.switch_backend(new_provider)
        self.mock_provider.lock_vault.assert_called_once()
        self.assertEqual(self.tray.provider, new_provider)
        self.mock_palette.set_provider.assert_called_once_with(new_provider)
        self.mock_main_window.set_provider.assert_called_once_with(new_provider)

    def test_switch_backend_when_main_window_lacks_set_provider(self):
        window_without_set_provider = QWidget()
        tray = SystemTrayManager(
            provider=self.mock_provider,
            palette_dialog=self.mock_palette,
            main_window=window_without_set_provider,
        )
        new_provider = MagicMock()
        tray.switch_backend(new_provider)
        self.assertEqual(tray.provider, new_provider)
        self.mock_palette.set_provider.assert_called_with(new_provider)
        tray.tray_icon.hide()

    def test_lock_action_clears_palette_and_locks(self):
        self.tray.lock_vault_now()
        self.mock_provider.lock_vault.assert_called_once()
        self.mock_palette.hide.assert_called_once()
        # Checks main_window lock or hide
        if hasattr(self.mock_main_window, "lock_vault"):
            self.mock_main_window.lock_vault.assert_called_once()
        elif hasattr(self.mock_main_window, "_lock_vault"):
            self.mock_main_window._lock_vault.assert_called_once()
        else:
            self.mock_main_window.hide.assert_called_once()

    def test_on_tray_activated_single_click(self):
        self.tray.on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
        self.mock_palette.show_centered.assert_called_once()

    def test_on_tray_activated_double_click(self):
        self.tray.on_tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
        self.mock_main_window.show.assert_called_once()
        self.mock_main_window.activateWindow.assert_called_once()

    @patch("PySide6.QtWidgets.QInputDialog.getItem")
    def test_prompt_switch_backend_cancelled(self, mock_get_item):
        mock_get_item.return_value = ("Local Database", False)
        with patch.object(self.tray, "switch_backend") as mock_switch:
            self.tray.prompt_switch_backend()
            mock_switch.assert_not_called()

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteVaultProvider")
    @patch("PySide6.QtWidgets.QInputDialog.getText")
    @patch("PySide6.QtWidgets.QInputDialog.getItem")
    def test_prompt_switch_backend_to_remote(self, mock_get_item, mock_get_text, mock_remote_provider_cls):
        # Current is local mock
        type(self.mock_provider).__name__ = "LocalVaultProvider"
        mock_get_item.return_value = ("Remote Server", True)
        mock_get_text.return_value = ("http://192.168.1.50:8080", True)
        mock_remote_instance = MagicMock()
        mock_remote_provider_cls.return_value = mock_remote_instance

        with patch.object(self.tray, "switch_backend") as mock_switch:
            self.tray.prompt_switch_backend()
            mock_remote_provider_cls.assert_called_once_with(server_url="http://192.168.1.50:8080")
            mock_switch.assert_called_once_with(mock_remote_instance)

    @patch("dev.abhishekraha.secretmanager.providers.LocalVaultProvider.LocalVaultProvider")
    @patch("PySide6.QtWidgets.QInputDialog.getItem")
    def test_prompt_switch_backend_to_local(self, mock_get_item, mock_local_provider_cls):
        # Current is remote mock
        type(self.mock_provider).__name__ = "RemoteVaultProvider"
        mock_get_item.return_value = ("Local Database", True)
        mock_local_instance = MagicMock()
        mock_local_provider_cls.return_value = mock_local_instance

        with patch.object(self.tray, "switch_backend") as mock_switch:
            self.tray.prompt_switch_backend()
            mock_local_provider_cls.assert_called_once()
            mock_switch.assert_called_once_with(mock_local_instance)

    @patch("PySide6.QtWidgets.QApplication.quit")
    def test_quit_application(self, mock_quit):
        self.tray.quit_application()
        self.mock_provider.lock_vault.assert_called_once()
        mock_quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
