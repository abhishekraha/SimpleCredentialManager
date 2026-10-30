import time
import unittest
from unittest.mock import MagicMock
from starlette.testclient import TestClient

from dev.abhishekraha.secretmanager.server.ServerApp import create_app
from dev.abhishekraha.secretmanager.server.TransportCrypto import encrypt_payload
from dev.abhishekraha.secretmanager.model.Secret import Secret


class TestServerApi(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.mock_registry = MagicMock()
        self.mock_session_manager = MagicMock()

        # Default registry mocks
        self.mock_registry.get_or_create_enrollment_token.return_value = "valid-secret-token"
        self.mock_registry.request_enrollment.return_value = {
            "device_id": "dev-12345678",
            "device_name": "TestDevice",
            "fingerprint": "abc123fingerprint",
            "device_token": "token-hex-32",
            "status": "PENDING",
        }
        self.mock_registry.is_device_approved.side_effect = lambda t: t == "approved-device-token"

        # Default session mocks
        self.mock_session_manager.create_session.return_value = "valid-session-token"
        self.mock_session_manager.validate_session.side_effect = lambda t: t == "valid-session-token"
        self.mock_session_manager.is_vault_unlocked.return_value = True

        # Default service mocks
        self.mock_service.is_initialized.return_value = True
        self.mock_service.is_unlocked.return_value = True
        self.mock_service.get_lockout_status.return_value = {
            "is_locked_out": False,
            "remaining_seconds": 0,
            "failed_attempts": 0,
            "remaining_attempts_before_lockout": 3,
        }
        self.mock_service.authenticate.return_value = (True, "Unlocked successfully")

        self.app = create_app(
            service=self.mock_service,
            registry=self.mock_registry,
            session_manager=self.mock_session_manager,
        )
        self.client = TestClient(self.app)

    def test_gatekeeper_blocks_unauthorized_endpoints_without_device_token(self):
        resp = self.client.get("/api/v1/auth/status")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Service unavailable", resp.json().get("detail", ""))

    def test_gatekeeper_blocks_unapproved_device_token(self):
        resp = self.client.get("/api/v1/auth/status", headers={"X-Device-Token": "unapproved-token"})
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Service unavailable", resp.json().get("detail", ""))

    def test_gatekeeper_allows_exempt_endpoints_without_token(self):
        # /openapi.json or docs should be exempt
        resp = self.client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)

    def test_enrollment_blocked_when_vault_not_initialized(self):
        self.mock_service.is_initialized.return_value = False
        resp = self.client.post("/api/v1/devices/enroll?secret=valid-secret-token", json={"device_name": "Phone"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("Vault is not initialized", resp.json().get("detail", ""))

        resp_get = self.client.get("/enroll")
        self.assertEqual(resp_get.status_code, 503)

    def test_enrollment_endpoint_requires_valid_secret(self):
        resp = self.client.post("/api/v1/devices/enroll?secret=wrong-secret", json={"device_name": "Phone"})
        self.assertEqual(resp.status_code, 403)

        resp2 = self.client.post("/api/v1/devices/enroll?secret=valid-secret-token", json={"device_name": "Phone"})
        self.assertEqual(resp2.status_code, 202)
        data = resp2.json()
        self.assertEqual(data["device_id"], "dev-12345678")
        self.assertEqual(data["device_token"], "token-hex-32")
        self.assertEqual(data["fingerprint"], "abc123fingerprint")

    def test_device_status_endpoint(self):
        # Missing token -> 404 / Service unavailable by gatekeeper
        resp = self.client.get("/api/v1/devices/status")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Service unavailable", resp.json().get("detail", ""))

        # Approved token -> 200 with approved=True
        resp_approved = self.client.get("/api/v1/devices/status", headers={"X-Device-Token": "approved-device-token"})
        self.assertEqual(resp_approved.status_code, 200)
        self.assertEqual(resp_approved.json(), {"approved": True})

    def test_auth_status_endpoint(self):
        resp = self.client.get("/api/v1/auth/status", headers={"X-Device-Token": "approved-device-token"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["unlocked"])
        self.assertIn("lockout", data)

    def test_auth_unlock_success(self):
        resp = self.client.post(
            "/api/v1/auth/unlock",
            headers={"X-Device-Token": "approved-device-token"},
            json={"password": "correct-password"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("unlocked"))
        self.assertIn("token", data)
        # Check cookie
        self.assertIn("scm_session", resp.cookies)
        self.assertEqual(resp.cookies["scm_session"], "valid-session-token")

    def test_auth_unlock_encrypted_payload_success(self):
        token = "approved-device-token"
        raw_payload = {"password": "correct-password"}
        encrypted = encrypt_payload(raw_payload, token)
        self.assertIn("iv", encrypted)
        self.assertIn("ciphertext", encrypted)

        resp = self.client.post(
            "/api/v1/auth/unlock",
            headers={"X-Device-Token": token},
            json=encrypted,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("unlocked"))
        self.assertIn("token", data)
        self.mock_service.authenticate.assert_called_with("correct-password")

    def test_auth_unlock_encrypted_payload_corrupted_fails(self):
        token = "approved-device-token"
        encrypted = {"iv": "invalid-iv", "ciphertext": "invalid-ct"}
        resp = self.client.post(
            "/api/v1/auth/unlock",
            headers={"X-Device-Token": token},
            json=encrypted,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Failed to decrypt transport payload", resp.json().get("detail", ""))

    def test_auth_unlock_failure(self):
        self.mock_service.authenticate.return_value = (False, "Invalid password")
        resp = self.client.post(
            "/api/v1/auth/unlock",
            headers={"X-Device-Token": "approved-device-token"},
            json={"password": "wrong-password"},
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertIn("lockout", data)

    def test_auth_lock(self):
        resp = self.client.post(
            "/api/v1/auth/lock",
            headers={
                "X-Device-Token": "approved-device-token",
                "Cookie": "scm_session=valid-session-token",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"unlocked": False})
        self.mock_service.lock_vault.assert_called()

    def test_secret_crud_endpoints(self):
        # 1. Secret requires session (without cookie or bearer token -> 401)
        resp = self.client.get(
            "/api/v1/secrets",
            headers={"X-Device-Token": "approved-device-token"},
        )
        self.assertEqual(resp.status_code, 401)

        headers = {
            "X-Device-Token": "approved-device-token",
            "Cookie": "scm_session=valid-session-token",
        }

        # 2. GET /api/v1/secrets (list)
        s1 = Secret("github", "user1", "pass1", "https://github.com", "my notes")
        self.mock_service.get_secret_records.return_value = [s1]
        resp_list = self.client.get("/api/v1/secrets", headers=headers)
        self.assertEqual(resp_list.status_code, 200)
        secrets_data = resp_list.json()
        self.assertEqual(len(secrets_data), 1)
        self.assertEqual(secrets_data[0]["name"], "github")

        # 3. GET /api/v1/secrets/{name}
        self.mock_service.get_secret.return_value = s1
        resp_get = self.client.get("/api/v1/secrets/github", headers=headers)
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.json()["name"], "github")

        # 4. POST /api/v1/secrets (create)
        resp_create = self.client.post(
            "/api/v1/secrets",
            headers=headers,
            json={
                "name": "google",
                "username": "user@gmail.com",
                "password": "secretpassword",
                "url": "https://google.com",
                "comments": "work email",
                "category": "login",
                "is_favorite": True,
            },
        )
        self.assertEqual(resp_create.status_code, 201)
        self.mock_service.add_secret.assert_called_with(
            name="google",
            username="user@gmail.com",
            password="secretpassword",
            url="https://google.com",
            comments="work email",
            category="login",
            is_favorite=True,
            totp_secret=None,
            tags=None,
        )

        # 5. PUT /api/v1/secrets/{name} (update)
        resp_update = self.client.put(
            "/api/v1/secrets/google",
            headers=headers,
            json={
                "username": "user2@gmail.com",
                "password": "newpassword",
            },
        )
        self.assertEqual(resp_update.status_code, 200)
        self.mock_service.update_secret.assert_called()

        # 6. DELETE /api/v1/secrets/{name}
        resp_del = self.client.delete("/api/v1/secrets/google", headers=headers)
        self.assertEqual(resp_del.status_code, 200)
        self.mock_service.delete_secret.assert_called_with("google")

    def test_totp_endpoint(self):
        headers = {
            "X-Device-Token": "approved-device-token",
            "Cookie": "scm_session=valid-session-token",
        }
        # Secret without TOTP
        s_no_totp = Secret("no_totp", "u", "p")
        self.mock_service.get_secret.return_value = s_no_totp
        resp_404 = self.client.get("/api/v1/totp/no_totp", headers=headers)
        self.assertEqual(resp_404.status_code, 404)

        # Secret with TOTP
        s_totp = Secret("totp_service", "u", "p", totp_secret="JBSWY3DPEHPK3PXP")
        self.mock_service.get_secret.return_value = s_totp
        resp_totp = self.client.get("/api/v1/totp/totp_service", headers=headers)
        self.assertEqual(resp_totp.status_code, 200)
        totp_data = resp_totp.json()
        self.assertIn("code", totp_data)
        self.assertIn("remaining_seconds", totp_data)
        self.assertEqual(len(totp_data["code"]), 6)

    def test_subpath_prefix_and_forwarded_prefix(self):
        app_subpath = create_app(
            service=self.mock_service,
            registry=self.mock_registry,
            session_manager=self.mock_session_manager,
            prefix="/password",
        )
        client_sub = TestClient(app_subpath)
        # Exempt endpoint under /password
        resp = client_sub.post("/password/api/v1/devices/enroll?secret=valid-secret-token", json={"device_name": "Phone"})
        self.assertEqual(resp.status_code, 202)

        # Exempt endpoint with X-Forwarded-Prefix
        client_root = TestClient(self.app)
        resp_fwd = client_root.post(
            "/custom-prefix/api/v1/devices/enroll?secret=valid-secret-token",
            headers={"X-Forwarded-Prefix": "/custom-prefix"},
            json={"device_name": "Tablet"},
        )
        self.assertEqual(resp_fwd.status_code, 202)


if __name__ == "__main__":
    unittest.main()
