import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
from dev.abhishekraha.secretmanager.providers.RemoteVaultProvider import RemoteVaultProvider

app = QApplication.instance() or QApplication([])


class TestModernUiProviderWiring(unittest.TestCase):
    def test_window_accepts_provider_argument(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
        mock_provider = MagicMock(spec=LocalVaultProvider)
        mock_provider.is_unlocked.return_value = True
        mock_provider.get_secret_records.return_value = []

        window = ModernMainWindow(provider=mock_provider)
        try:
            self.assertEqual(window.provider, mock_provider)
            self.assertEqual(window.service, mock_provider)
            self.assertIn("Local DB", window.statusBar().currentMessage())
        finally:
            window.close()

    def test_window_defaults_to_local_vault_provider(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
        with patch("dev.abhishekraha.secretmanager.ui.ModernMainWindow.LocalVaultProvider") as mock_local_cls:
            mock_inst = MagicMock(spec=LocalVaultProvider)
            mock_inst.is_unlocked.return_value = True
            mock_inst.get_secret_records.return_value = []
            mock_local_cls.return_value = mock_inst

            window = ModernMainWindow()
            try:
                self.assertEqual(window.provider, mock_inst)
                mock_local_cls.assert_called_once()
            finally:
                window.close()

    def test_set_provider_updates_provider_and_status_bar(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
        local_mock = MagicMock(spec=LocalVaultProvider)
        local_mock.is_unlocked.return_value = True
        local_mock.get_secret_records.return_value = []

        window = ModernMainWindow(provider=local_mock)
        try:
            self.assertIn("Local DB", window.statusBar().currentMessage())

            remote_mock = MagicMock(spec=RemoteVaultProvider)
            remote_mock.is_unlocked.return_value = True
            remote_mock.get_secret_records.return_value = []
            remote_mock.client = MagicMock()
            remote_mock.client.server_url = "https://scm.internal:8080"

            window.set_provider(remote_mock)
            self.assertEqual(window.provider, remote_mock)
            self.assertEqual(window.service, remote_mock)
            self.assertIn("Remote Server", window.statusBar().currentMessage())
            self.assertIn("https://scm.internal:8080", window.statusBar().currentMessage())
        finally:
            window.close()

    def test_open_secret_detail_selects_and_displays_secret(self):
        from dev.abhishekraha.secretmanager.ui.ModernMainWindow import ModernMainWindow
        from dev.abhishekraha.secretmanager.model.Secret import Secret
        provider_mock = MagicMock(spec=LocalVaultProvider)
        provider_mock.is_unlocked.return_value = True
        sec1 = Secret(name="AWS Root", username="root", password="pwd", category="cloud")
        sec2 = Secret(name="GitHub", username="octo", password="pwd", category="login")
        provider_mock.get_secret_records.return_value = [sec1, sec2]
        provider_mock.get_secret.side_effect = lambda n: sec1 if n == "AWS Root" else sec2 if n == "GitHub" else None

        window = ModernMainWindow(provider=provider_mock)
        try:
            window.open_secret_detail("GitHub")
            self.assertEqual(window.detail_title.text(), "GitHub")
            self.assertEqual(window.username_val.text(), "octo")
            # Verify secret list selected item is GitHub
            from PySide6.QtCore import Qt
            self.assertEqual(window.secret_list.currentItem().data(Qt.UserRole), "GitHub")
        finally:
            window.close()


class TestUiCliArgsParsing(unittest.TestCase):
    def test_parse_arguments_defaults(self):
        import SimpleCredentialManagerUi as ui_module
        args = ui_module.parse_arguments([])
        self.assertIsNone(args.remote)
        self.assertFalse(args.palette)
        self.assertFalse(args.tray)
        self.assertFalse(args.tkinter)
        self.assertFalse(args.classic)
        self.assertFalse(args.modern)

    def test_parse_arguments_remote(self):
        import SimpleCredentialManagerUi as ui_module
        args = ui_module.parse_arguments(["--remote", "https://vault.corp:9000"])
        self.assertEqual(args.remote, "https://vault.corp:9000")

    def test_parse_arguments_palette_and_tray(self):
        import SimpleCredentialManagerUi as ui_module
        args = ui_module.parse_arguments(["--palette", "--tray"])
        self.assertTrue(args.palette)
        self.assertTrue(args.tray)


class TestRunModernUiIntegrationWiring(unittest.TestCase):
    @patch("dev.abhishekraha.secretmanager.utils.GlobalHotkeyService.GlobalHotkeyService")
    @patch("dev.abhishekraha.secretmanager.ui.SystemTrayManager.SystemTrayManager")
    @patch("dev.abhishekraha.secretmanager.ui.ModernMainWindow.ModernMainWindow")
    @patch("dev.abhishekraha.secretmanager.ui.CommandPaletteDialog.CommandPaletteDialog")
    @patch("PySide6.QtWidgets.QApplication.exec")
    def test_run_modern_ui_wires_services_and_signals(
        self,
        mock_qapp_exec,
        mock_palette_cls,
        mock_window_cls,
        mock_tray_cls,
        mock_hotkey_cls,
    ):
        from dev.abhishekraha.secretmanager.ui import run_modern_ui

        mock_provider = MagicMock(spec=LocalVaultProvider)
        mock_provider.is_unlocked.return_value = True

        mock_palette = MagicMock()
        mock_palette_cls.return_value = mock_palette

        mock_window = MagicMock()
        mock_window_cls.return_value = mock_window

        mock_hotkey = MagicMock()
        mock_hotkey_cls.return_value = mock_hotkey

        mock_qapp_exec.return_value = 0

        run_modern_ui(provider=mock_provider, start_palette=True)

        mock_palette_cls.assert_called_once_with(provider=mock_provider)
        mock_window_cls.assert_called_once_with(provider=mock_provider)
        mock_tray_cls.assert_called_once_with(
            provider=mock_provider,
            palette_dialog=mock_palette,
            main_window=mock_window,
        )

        mock_palette.open_full_window_requested.connect.assert_called_once_with(
            mock_window.open_secret_detail
        )
        mock_hotkey.hotkey_triggered.connect.assert_called_once_with(
            mock_palette.show_centered
        )
        mock_hotkey.start.assert_called_once()
        mock_palette.show_centered.assert_called_once()

