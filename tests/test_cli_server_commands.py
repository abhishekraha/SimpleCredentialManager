import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dev.abhishekraha.secretmanager.cli.ModernCli import app


class TestCliServerCommands(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner(env={"COLUMNS": "160"})

    def test_server_help(self):
        result = self.runner.invoke(app, ["server", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("start", result.output)
        self.assertIn("devices", result.output)

    def test_server_devices_help(self):
        result = self.runner.invoke(app, ["server", "devices", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("approve", result.output)
        self.assertIn("revoke", result.output)
        self.assertIn("token", result.output)

    @patch("uvicorn.run")
    @patch("dev.abhishekraha.secretmanager.cli.ModernCli.create_app")
    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.get_or_create_enrollment_token")
    def test_server_start_default_options(self, mock_get_token, mock_create_app, mock_uvicorn_run):
        mock_get_token.return_value = "test-enroll-secret"
        mock_fastapi_app = MagicMock()
        mock_create_app.return_value = mock_fastapi_app

        result = self.runner.invoke(app, ["server", "start"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("127.0.0.1", result.output)
        self.assertIn("8080", result.output)
        self.assertIn("/enroll?secret=test-enroll-secret", result.output)

        mock_create_app.assert_called_once_with(prefix="")
        mock_uvicorn_run.assert_called_once_with(mock_fastapi_app, host="127.0.0.1", port=8080, root_path="")

    @patch("uvicorn.run")
    @patch("dev.abhishekraha.secretmanager.cli.ModernCli.create_app")
    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.get_or_create_enrollment_token")
    def test_server_start_custom_options(self, mock_get_token, mock_create_app, mock_uvicorn_run):
        mock_get_token.return_value = "my-secret-token"
        mock_fastapi_app = MagicMock()
        mock_create_app.return_value = mock_fastapi_app

        result = self.runner.invoke(app, ["server", "start", "--host", "0.0.0.0", "--port", "9090", "--prefix", "/password", "--reload"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("0.0.0.0", result.output)
        self.assertIn("9090", result.output)
        self.assertIn("/password/enroll?secret=my-secret-token", result.output)

        mock_create_app.assert_called_once_with(prefix="/password")
        mock_uvicorn_run.assert_called_once_with(mock_fastapi_app, host="0.0.0.0", port=9090, root_path="/password", reload=True)

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.list_devices")
    def test_server_devices_list_empty(self, mock_list):
        mock_list.return_value = []
        result = self.runner.invoke(app, ["server", "devices", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("No registered devices found" in result.output or "Device ID" in result.output)

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.list_devices")
    def test_server_devices_list_populated(self, mock_list):
        mock_list.return_value = [
            {
                "device_id": "dev-001",
                "device_name": "Pixel 8",
                "fingerprint": "abc123def456",
                "status": "PENDING",
                "client_ip": "192.168.1.10",
                "created_at": "2026-10-30 12:00:00",
                "updated_at": "2026-10-30 12:00:00",
            },
            {
                "device_id": "dev-002",
                "device_name": "Work Laptop",
                "fingerprint": "789xyz012345",
                "status": "APPROVED",
                "client_ip": "192.168.1.11",
                "created_at": "2026-10-30 11:00:00",
                "updated_at": "2026-10-30 11:05:00",
            },
            {
                "device_id": "dev-003",
                "device_name": "Old Tablet",
                "fingerprint": "fedcba987654",
                "status": "REVOKED",
                "client_ip": "192.168.1.12",
                "created_at": "2026-10-30 10:00:00",
                "updated_at": "2026-10-30 10:15:00",
            },
        ]
        result = self.runner.invoke(app, ["server", "devices", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("dev-001", result.output)
        self.assertIn("Pixel 8", result.output)
        self.assertIn("PENDING", result.output)
        self.assertIn("dev-002", result.output)
        self.assertIn("Work Laptop", result.output)
        self.assertIn("APPROVED", result.output)
        self.assertIn("dev-003", result.output)
        self.assertIn("Old Tablet", result.output)
        self.assertIn("REVOKED", result.output)

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.approve_device")
    def test_server_devices_approve_success(self, mock_approve):
        mock_approve.return_value = True
        result = self.runner.invoke(app, ["server", "devices", "approve", "dev-001"])
        self.assertEqual(result.exit_code, 0)
        mock_approve.assert_called_once_with("dev-001")
        self.assertIn("approved", result.output.lower())

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.approve_device")
    def test_server_devices_approve_not_found(self, mock_approve):
        mock_approve.return_value = False
        result = self.runner.invoke(app, ["server", "devices", "approve", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        mock_approve.assert_called_once_with("nonexistent")
        self.assertIn("not found", result.output.lower())

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.revoke_device")
    def test_server_devices_revoke_success(self, mock_revoke):
        mock_revoke.return_value = True
        result = self.runner.invoke(app, ["server", "devices", "revoke", "dev-001"])
        self.assertEqual(result.exit_code, 0)
        mock_revoke.assert_called_once_with("dev-001")
        self.assertIn("revoked", result.output.lower())

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.revoke_device")
    def test_server_devices_revoke_not_found(self, mock_revoke):
        mock_revoke.return_value = False
        result = self.runner.invoke(app, ["server", "devices", "revoke", "nonexistent"])
        self.assertNotEqual(result.exit_code, 0)
        mock_revoke.assert_called_once_with("nonexistent")
        self.assertIn("not found", result.output.lower())

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.get_or_create_enrollment_token")
    def test_server_devices_token_show_default(self, mock_get_token):
        mock_get_token.return_value = "current-enrollment-token"
        result = self.runner.invoke(app, ["server", "devices", "token"])
        self.assertEqual(result.exit_code, 0)
        mock_get_token.assert_called_once()
        self.assertIn("current-enrollment-token", result.output)

    @patch("dev.abhishekraha.secretmanager.server.DeviceRegistry.DeviceRegistry.rotate_enrollment_token")
    def test_server_devices_token_rotate(self, mock_rotate_token):
        mock_rotate_token.return_value = "newly-rotated-enrollment-token"
        result = self.runner.invoke(app, ["server", "devices", "token", "--rotate"])
        self.assertEqual(result.exit_code, 0)
        mock_rotate_token.assert_called_once()
        self.assertIn("newly-rotated-enrollment-token", result.output)


if __name__ == "__main__":
    unittest.main()
