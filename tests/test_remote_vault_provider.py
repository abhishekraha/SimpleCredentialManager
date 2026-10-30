import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.providers.RemoteHttpClient import RemoteHttpClient
from dev.abhishekraha.secretmanager.providers.RemoteVaultProvider import RemoteVaultProvider
from dev.abhishekraha.secretmanager.server.TransportCrypto import encrypt_payload, decrypt_payload


class TestRemoteHttpClient(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "remote_client.json"
        self.server_url = "http://127.0.0.1:8080"
        self.client = RemoteHttpClient(
            server_url=self.server_url,
            config_path=self.config_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_and_config_permissions(self):
        self.assertEqual(self.client.server_url, self.server_url)
        self.assertFalse(self.client.is_enrolled())

        # Save config and verify file created
        self.client.device_id = "dev-12345"
        self.client.device_token = "token-secret-abc"
        self.client.save_config()

        self.assertTrue(self.config_path.exists())
        # Check permissions on POSIX
        if os.name == "posix":
            file_mode = stat.S_IMODE(self.config_path.stat().st_mode)
            self.assertEqual(file_mode, 0o600)

        # Reloading client loads the saved values
        reloaded = RemoteHttpClient(config_path=self.config_path)
        self.assertEqual(reloaded.device_id, "dev-12345")
        self.assertEqual(reloaded.device_token, "token-secret-abc")
        self.assertTrue(reloaded.is_enrolled())

    @patch("httpx.Client.post")
    def test_enroll_device_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 202
        mock_resp.json.return_value = {
            "device_id": "dev-enrolled-1",
            "device_token": "token-9999",
            "status": "PENDING",
        }
        mock_post.return_value = mock_resp

        result = self.client.enroll_device("enroll-secret-token", "My-Laptop")
        self.assertEqual(result["device_id"], "dev-enrolled-1")
        self.assertEqual(self.client.device_id, "dev-enrolled-1")
        self.assertEqual(self.client.device_token, "token-9999")
        self.assertTrue(self.config_path.exists())

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("secret=enroll-secret-token", args[0])
        self.assertEqual(kwargs["json"], {"device_name": "My-Laptop"})

    @patch("httpx.Client.post")
    def test_post_encrypted_success(self, mock_post):
        self.client.device_token = "test-device-token-123"

        # Prepare encrypted response
        plain_response = {"success": True, "token": "session-jwt-1"}
        enc_response = encrypt_payload(plain_response, self.client.device_token)

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = enc_response
        mock_post.return_value = mock_resp

        payload = {"password": "MasterPassword123!"}
        result = self.client.post_encrypted("/api/v1/auth/unlock", payload, session_token="existing-session")

        self.assertEqual(result, plain_response)
        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertTrue(url.endswith("/api/v1/auth/unlock"))
        self.assertEqual(kwargs["headers"]["X-Device-Token"], self.client.device_token)
        self.assertEqual(kwargs["headers"]["X-Session-Token"], "existing-session")
        # Ensure outbound payload was encrypted with iv and ciphertext
        sent_body = kwargs["json"]
        self.assertIn("iv", sent_body)
        self.assertIn("ciphertext", sent_body)
        decrypted_sent = decrypt_payload(sent_body, self.client.device_token)
        self.assertEqual(decrypted_sent, payload)

    @patch("httpx.Client.post")
    def test_post_encrypted_connection_failure(self, mock_post):
        self.client.device_token = "test-device-token"
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with self.assertRaises(ConnectionError):
            self.client.post_encrypted("/api/v1/auth/unlock", {"password": "pass"})

    @patch("httpx.Client.post")
    def test_post_encrypted_unauthorized_gatekeeper(self, mock_post):
        self.client.device_token = "test-device-token"
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Service unavailable"}
        mock_post.return_value = mock_resp

        with self.assertRaises(PermissionError):
            self.client.post_encrypted("/api/v1/secrets", {"name": "test"})

    @patch("httpx.Client.put")
    @patch("httpx.Client.delete")
    def test_put_and_delete(self, mock_delete, mock_put):
        self.client.device_token = "token-xyz"
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_put.return_value = mock_resp
        mock_delete.return_value = mock_resp

        res_put = self.client.put_encrypted("/api/v1/secrets/test", {"password": "pwd"}, session_token="tok")
        self.assertEqual(res_put, {"status": "ok"})
        mock_put.assert_called_once()

        res_del = self.client.delete("/api/v1/secrets/test", session_token="tok")
        self.assertEqual(res_del, {"status": "ok"})
        mock_delete.assert_called_once()

    @patch("httpx.Client.get")
    def test_check_device_status(self, mock_get):
        self.client.device_token = "token-xyz"
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"approved": True}
        mock_get.return_value = mock_resp

        status = self.client.check_device_status()
        self.assertTrue(status["approved"])


class TestRemoteVaultProvider(unittest.TestCase):
    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_implements_interface(self, mock_client_cls):
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        self.assertIsInstance(provider, VaultDataProvider)

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_authenticate_and_fetch_secrets(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.post_encrypted.side_effect = [
            {"success": True, "token": "session-xyz", "message": "Unlocked"},
            {"items": [{"name": "gmail", "username": "me@example.com", "category": "login", "is_favorite": False}]},
            {"items": [{"name": "gmail", "username": "me@example.com", "category": "login", "is_favorite": False}]},
        ]
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        ok, msg = provider.authenticate("MasterPass123!")
        self.assertTrue(ok)
        self.assertTrue(provider.is_unlocked())

        secrets = provider.get_secret_records("gm")
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0].name, "gmail")
        self.assertEqual(secrets[0].username, "me@example.com")

        # Test secret names
        names = provider.get_secret_names()
        self.assertEqual(names, ["gmail"])

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_server_unreachable_zero_trace(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.post_encrypted.side_effect = httpx.ConnectError("Connection refused")
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")

        # Locked initially
        self.assertFalse(provider.is_unlocked())

        with self.assertRaises(ConnectionError):
            provider.get_secret_records()

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_auth_failure_does_not_set_session_token(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.post_encrypted.return_value = {
            "unlocked": False,
            "detail": "Invalid master password",
        }
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        ok, msg = provider.authenticate("WrongPass")
        self.assertFalse(ok)
        self.assertIn("Invalid master password", msg)
        self.assertFalse(provider.is_unlocked())
        self.assertIsNone(provider._session_token)

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_lock_vault_zeroes_session_token(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.post_encrypted.return_value = {"unlocked": True, "token": "session-active-123"}

        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        provider.authenticate("CorrectPass")
        self.assertTrue(provider.is_unlocked())
        self.assertEqual(provider._session_token, "session-active-123")

        # Lock vault
        provider.lock_vault()
        self.assertFalse(provider.is_unlocked())
        self.assertIsNone(provider._session_token)
        mock_client.post_encrypted.assert_called_with("/api/v1/auth/lock", {}, session_token="session-active-123")

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_crud_operations(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.post_encrypted.return_value = {"unlocked": True, "token": "token-1"}

        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        provider.authenticate("Pass")

        # Add secret
        provider.add_secret("aws", "admin", "pwd123", url="https://aws.amazon.com")
        mock_client.post_encrypted.assert_called_with(
            "/api/v1/secrets",
            {
                "name": "aws",
                "username": "admin",
                "password": "pwd123",
                "url": "https://aws.amazon.com",
                "comments": "",
                "category": "login",
                "is_favorite": False,
                "totp_secret": None,
                "tags": [],
            },
            session_token="token-1",
        )

        # Update secret
        provider.update_secret("aws", password="newpwd")
        mock_client.put_encrypted.assert_called_with(
            "/api/v1/secrets/aws",
            {"password": "newpwd"},
            session_token="token-1",
        )

        # Delete secret
        provider.delete_secret("aws")
        mock_client.delete.assert_called_with(
            "/api/v1/secrets/aws",
            session_token="token-1",
        )

        # Get secret
        mock_client.get.return_value = {
            "name": "aws",
            "username": "admin",
            "password": "pwd",
            "category": "cloud",
            "is_favorite": True,
        }
        secret = provider.get_secret("aws")
        self.assertIsNotNone(secret)
        self.assertEqual(secret.name, "aws")
        self.assertEqual(secret.category, "cloud")

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_unsupported_master_password_operations(self, mock_client_cls):
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        with self.assertRaises(NotImplementedError):
            provider.setup_master_password("a", "b")
        with self.assertRaises(NotImplementedError):
            provider.change_master_password("a", "b", "c")

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_lifecycle_and_health_audit(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.get.side_effect = [
            {"status": "ok"},  # healthz for initialize
            {"status": "ok"},  # healthz for is_initialized
            {"lockout": {"locked": False, "remaining_seconds": 0}},  # auth status
            [
                {"name": "github", "username": "dev", "password": "weak", "category": "login"},
            ],  # get_secret_records
        ]
        mock_client.post_encrypted.return_value = {"unlocked": True, "token": "session-1"}

        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        self.assertTrue(provider.initialize())
        self.assertTrue(provider.is_initialized())

        lockout = provider.get_lockout_status()
        self.assertFalse(lockout["locked"])

        # Authenticate and audit health
        provider.authenticate("GoodPassword123!")
        audit_res = provider.audit_health()
        self.assertIn("health_score", audit_res)
        self.assertIn("weak_secrets", audit_res)

        # Generate password
        pwd = provider.generate_password(length=24)
        self.assertEqual(len(pwd), 24)

    @patch("dev.abhishekraha.secretmanager.providers.RemoteVaultProvider.RemoteHttpClient")
    def test_locked_guardrails(self, mock_client_cls):
        provider = RemoteVaultProvider(server_url="http://127.0.0.1:8080")
        with self.assertRaises(RuntimeError):
            provider.get_secret("secret")
        with self.assertRaises(RuntimeError):
            provider.add_secret("name", "user", "pass")
        with self.assertRaises(RuntimeError):
            provider.update_secret("name", password="pass")
        with self.assertRaises(RuntimeError):
            provider.delete_secret("name")


if __name__ == "__main__":
    unittest.main()
