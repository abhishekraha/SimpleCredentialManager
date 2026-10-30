import time
import unittest
from unittest.mock import MagicMock, patch

from dev.abhishekraha.secretmanager.server.SessionManager import ServerSessionManager


class TestServerSessionManager(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.mock_service.is_unlocked.return_value = True
        self.session_manager = ServerSessionManager(
            service=self.mock_service,
            idle_timeout_seconds=60
        )

    def test_create_session(self):
        token = self.session_manager.create_session("device-123")
        self.assertTrue(token and isinstance(token, str))
        self.assertGreaterEqual(len(token), 32)
        
        session = self.session_manager.get_session(token)
        self.assertIsNotNone(session)
        self.assertEqual(session["device_id"], "device-123")
        self.assertAlmostEqual(session["created_at"], time.time(), delta=2.0)
        self.assertAlmostEqual(session["last_active"], time.time(), delta=2.0)

    def test_validate_session_active(self):
        token = self.session_manager.create_session("device-123")
        session_before = self.session_manager.get_session(token)
        initial_last_active = session_before["last_active"]
        
        time.sleep(0.01)
        self.assertTrue(self.session_manager.validate_session(token))
        
        session_after = self.session_manager.get_session(token)
        self.assertGreaterEqual(session_after["last_active"], initial_last_active)

    def test_validate_session_invalid_token(self):
        self.assertFalse(self.session_manager.validate_session("non-existent-token"))

    def test_validate_session_expired(self):
        mgr = ServerSessionManager(
            service=self.mock_service,
            idle_timeout_seconds=1
        )
        token = mgr.create_session("device-abc")
        session = mgr.get_session(token)
        # Artificially age the session
        session["last_active"] = time.time() - 2.0

        # validate should return False and terminate the expired session
        self.assertFalse(mgr.validate_session(token))
        self.assertIsNone(mgr.get_session(token))
        # Vault lock should have been triggered because 0 active sessions remain
        self.mock_service.lock_vault.assert_called()

    def test_terminate_session_locks_vault_when_last_session_removed(self):
        token1 = self.session_manager.create_session("device-1")
        token2 = self.session_manager.create_session("device-2")

        # Terminate token1; token2 still active -> do NOT lock vault
        self.session_manager.terminate_session(token1)
        self.mock_service.lock_vault.assert_not_called()
        self.assertIsNone(self.session_manager.get_session(token1))
        self.assertIsNotNone(self.session_manager.get_session(token2))

        # Terminate token2; 0 sessions remain -> lock vault and clear derived key
        with patch("dev.abhishekraha.secretmanager.codec.CodecUtils.clear_derived_key") as mock_clear:
            self.session_manager.terminate_session(token2)
            self.mock_service.lock_vault.assert_called_once()
            mock_clear.assert_called_once()

    def test_check_and_sweep_expired(self):
        mgr = ServerSessionManager(
            service=self.mock_service,
            idle_timeout_seconds=5
        )
        token1 = mgr.create_session("device-1")
        token2 = mgr.create_session("device-2")

        # Expire token1 only
        mgr.get_session(token1)["last_active"] = time.time() - 10.0

        swept_count = mgr.check_and_sweep_expired()
        self.assertEqual(swept_count, 1)
        self.assertIsNone(mgr.get_session(token1))
        self.assertIsNotNone(mgr.get_session(token2))
        self.mock_service.lock_vault.assert_not_called()

        # Expire token2 and sweep -> locks vault
        mgr.get_session(token2)["last_active"] = time.time() - 10.0
        with patch("dev.abhishekraha.secretmanager.codec.CodecUtils.clear_derived_key") as mock_clear:
            swept_count2 = mgr.check_and_sweep_expired()
            self.assertEqual(swept_count2, 1)
            self.assertIsNone(mgr.get_session(token2))
            self.mock_service.lock_vault.assert_called_once()
            mock_clear.assert_called_once()

    def test_is_vault_unlocked(self):
        self.mock_service.is_unlocked.return_value = True
        self.assertTrue(self.session_manager.is_vault_unlocked())

        self.mock_service.is_unlocked.return_value = False
        self.assertFalse(self.session_manager.is_vault_unlocked())

        # When service is None
        mgr_no_svc = ServerSessionManager(service=None)
        self.assertFalse(mgr_no_svc.is_vault_unlocked())

    def test_active_session_count(self):
        self.assertEqual(self.session_manager.active_session_count(), 0)
        token = self.session_manager.create_session("device-1")
        self.assertEqual(self.session_manager.active_session_count(), 1)
        self.session_manager.terminate_session(token)
        self.assertEqual(self.session_manager.active_session_count(), 0)


if __name__ == "__main__":
    unittest.main()
