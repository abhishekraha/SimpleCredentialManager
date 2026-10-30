import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
from dev.abhishekraha.secretmanager.providers.RemoteVaultProvider import RemoteVaultProvider
from dev.abhishekraha.secretmanager.ui.SystemTrayManager import SystemTrayManager
from dev.abhishekraha.secretmanager.ui.CommandPaletteDialog import CommandPaletteDialog
from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
from dev.abhishekraha.secretmanager.model.Secret import Secret

app = QApplication.instance() or QApplication([])

class TestUnifiedDesktopClientE2E(unittest.TestCase):
    def setUp(self):
        self.mock_local = MagicMock(spec=LocalVaultProvider)
        self.mock_local.is_unlocked.return_value = True
        local_secret = Secret(name="Local Secret", username="alice", password="local_secret_password")
        self.mock_local.get_secret.return_value = local_secret
        self.mock_local.get_secret_records.return_value = [local_secret]

        self.mock_remote = MagicMock(spec=RemoteVaultProvider)
        self.mock_remote.is_unlocked.return_value = True
        mock_client = MagicMock()
        mock_client.server_url = "https://scm.internal:8080"
        self.mock_remote.client = mock_client
        remote_secret = Secret(name="Remote Secret", username="bob", password="remote_secret_password")
        self.mock_remote.get_secret.return_value = remote_secret
        self.mock_remote.get_secret_records.return_value = [remote_secret]

    def test_full_lifecycle_and_backend_switching(self):
        palette = CommandPaletteDialog(provider=self.mock_local)
        window = ModernMainWindow(provider=self.mock_local)
        tray = SystemTrayManager(provider=self.mock_local, palette_dialog=palette, main_window=window)

        # 1. Initial State Verification (Local Mode)
        self.assertEqual(tray.provider, self.mock_local)
        self.assertEqual(palette.provider, self.mock_local)
        self.assertEqual(window.provider, self.mock_local)
        self.assertIn("Local DB", window.statusBar().currentMessage())

        # 2. In-place backend switch to Remote Provider
        tray.switch_backend(self.mock_remote)

        # Previous provider must be locked to purge memory
        self.mock_local.lock_vault.assert_called_once()

        # All surfaces must now point to remote provider
        self.assertEqual(tray.provider, self.mock_remote)
        self.assertEqual(palette.provider, self.mock_remote)
        self.assertEqual(window.provider, self.mock_remote)
        self.assertIn("Remote Server", window.statusBar().currentMessage())

        # 3. Command Palette search under Remote Provider
        palette.search_input.setText("Remote")
        self.assertEqual(palette.results_list.count(), 1)
        self.assertIn("Remote Secret (bob)", palette.results_list.item(0).text())

        # Clean up
        palette.close()
        window.close()
        tray.tray_icon.hide()

if __name__ == "__main__":
    unittest.main()
