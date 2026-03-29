import unittest
from unittest.mock import patch

from dev.abhishekraha.secretmanager.utils.Utils import copy_to_clipboard


class ClipboardUtilsTests(unittest.TestCase):
    @patch("dev.abhishekraha.secretmanager.utils.Utils.subprocess.run")
    @patch("dev.abhishekraha.secretmanager.utils.Utils.platform.system", return_value="Windows")
    def test_copy_to_clipboard_uses_windows_clip_command(self, mock_platform, mock_run):
        self.assertTrue(copy_to_clipboard("secret-value"))
        mock_run.assert_called_once_with(
            ["clip"],
            input="secret-value",
            text=True,
            check=True,
            capture_output=True,
        )

    @patch("dev.abhishekraha.secretmanager.utils.Utils._copy_with_tkinter", return_value=False)
    @patch(
        "dev.abhishekraha.secretmanager.utils.Utils.subprocess.run",
        side_effect=FileNotFoundError,
    )
    @patch(
        "dev.abhishekraha.secretmanager.utils.Utils.platform.system",
        return_value="Darwin",
    )
    def test_copy_to_clipboard_returns_false_when_all_backends_fail(
        self,
        mock_platform,
        mock_run,
        mock_tkinter_copy,
    ):
        self.assertFalse(copy_to_clipboard("secret-value"))
        mock_tkinter_copy.assert_called_once_with("secret-value")


if __name__ == "__main__":
    unittest.main()
