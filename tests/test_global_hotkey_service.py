import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from dev.abhishekraha.secretmanager.utils.GlobalHotkeyService import (
    GlobalHotkeyService,
    get_active_screen_geometry,
)

app = QApplication.instance() or QApplication([])


class TestGlobalHotkeyService(unittest.TestCase):
    def test_hotkey_service_initialization(self):
        service = GlobalHotkeyService(hotkey="<ctrl>+<shift>+<space>")
        self.assertFalse(service.is_active())
        self.assertEqual(service.hotkey, "<ctrl>+<shift>+<space>")

    def test_hotkey_service_fallback_when_pynput_missing(self):
        with patch.dict("sys.modules", {"pynput": None, "pynput.keyboard": None}):
            service = GlobalHotkeyService()
            self.assertFalse(service.is_active())
            # Should not crash on start or stop
            service.start()
            self.assertFalse(service.is_active())
            service.stop()
            self.assertFalse(service.is_active())

    def test_hotkey_service_fallback_when_listener_fails(self):
        with patch("pynput.keyboard.GlobalHotKeys", side_effect=Exception("Wayland not supported")):
            service = GlobalHotkeyService()
            service.start()
            self.assertFalse(service.is_active())
            service.stop()

    def test_hotkey_service_lifecycle_mocked(self):
        mock_listener = MagicMock()
        with patch("pynput.keyboard.GlobalHotKeys", return_value=mock_listener) as mock_ghk_cls:
            service = GlobalHotkeyService(hotkey="<ctrl>+<alt>+<space>")
            service.start()
            self.assertTrue(service.is_active())
            mock_listener.start.assert_called_once()
            
            # Verify listener was created with the hotkey mapping
            mock_ghk_cls.assert_called_once()
            args, _ = mock_ghk_cls.call_args
            self.assertIn("<ctrl>+<alt>+<space>", args[0])

            # Trigger callback and verify signal
            signal_emitted = []
            service.hotkey_triggered.connect(lambda: signal_emitted.append(True))
            args[0]["<ctrl>+<alt>+<space>"]()
            self.assertEqual(len(signal_emitted), 1)

            # Stop lifecycle
            service.stop()
            mock_listener.stop.assert_called_once()
            self.assertFalse(service.is_active())

    def test_screen_placement_utility(self):
        # Geometry should return a valid QRect with positive dimensions
        rect = get_active_screen_geometry()
        self.assertIsInstance(rect, QRect)
        self.assertGreater(rect.width(), 0)
        self.assertGreater(rect.height(), 0)

    @patch("PySide6.QtGui.QGuiApplication.screenAt")
    @patch("PySide6.QtGui.QGuiApplication.primaryScreen")
    def test_screen_placement_fallback_to_primary(self, mock_primary, mock_screen_at):
        mock_screen_at.return_value = None
        mock_screen = MagicMock()
        mock_screen.geometry.return_value = QRect(0, 0, 1920, 1080)
        mock_primary.return_value = mock_screen

        rect = get_active_screen_geometry()
        self.assertEqual(rect.width(), 1920)
        self.assertEqual(rect.height(), 1080)
        mock_primary.assert_called_once()

    @patch("PySide6.QtGui.QGuiApplication.screenAt")
    @patch("PySide6.QtGui.QGuiApplication.primaryScreen")
    def test_screen_placement_fallback_when_no_screens(self, mock_primary, mock_screen_at):
        mock_screen_at.return_value = None
        mock_primary.return_value = None

        rect = get_active_screen_geometry()
        self.assertEqual(rect, QRect(0, 0, 1920, 1080))


if __name__ == "__main__":
    unittest.main()
