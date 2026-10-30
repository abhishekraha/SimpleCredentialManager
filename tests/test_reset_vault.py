from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dev.abhishekraha.secretmanager.codec import CodecUtils
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    FAILED_AUTH_LOCKOUT_BASE_SECONDS,
    FAILED_AUTH_LOCKOUT_MAX_SECONDS,
    FAILED_AUTH_LOCKOUT_THRESHOLD,
)
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.storage.SqliteVaultStorage import SqliteVaultStorage


class ResetVaultAndLockoutPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.mock_app_home = self.temp_path / "home"
        self.mock_app_config = self.temp_path / "config"
        self.mock_app_home.mkdir(parents=True, exist_ok=True)
        self.mock_app_config.mkdir(parents=True, exist_ok=True)

        self.mock_meta = self.mock_app_config / ".simpleCredentialManager.metadata"
        self.mock_secret = self.mock_app_home / ".simpleCredentialManager.secret"
        self.mock_db = self.mock_app_home / "vault.scmdb"

        self.patches = [
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.APP_HOME_DIR", self.mock_app_home),
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.APP_CONFIG_DIR", self.mock_app_config),
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.SECRET_MANAGER_META_DATA", self.mock_meta),
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.SECRET_FILE", self.mock_secret),
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.VAULT_DB_FILE", self.mock_db),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.APP_HOME_DIR", self.mock_app_home),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.APP_CONFIG_DIR", self.mock_app_config),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_MANAGER_META_DATA", self.mock_meta),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_FILE", self.mock_secret),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.VAULT_DB_FILE", self.mock_db),
        ]
        for p in self.patches:
            p.start()

        self.master_pwd = "CorrectMasterPassword123!"
        self.service = SecretManagerService(client_name="test_reset")
        self.service.setup_master_password(self.master_pwd, self.master_pwd)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        CodecUtils.clear_derived_key()
        self.temp_dir.cleanup()

    def test_reset_vault_and_wipe_all_cleans_files_and_resets_state(self):
        # Authenticate and add a secret
        success, _ = self.service.authenticate(self.master_pwd)
        self.assertTrue(success)
        self.service.add_secret("Email", "alice@example.com", "SecretPass123!")
        self.assertTrue(self.mock_meta.exists())
        self.assertTrue(self.mock_secret.exists())

        # Also create dummy auxiliary files (wal, shm, backups)
        wal_file = Path(f"{self.mock_db}-wal")
        shm_file = Path(f"{self.mock_db}-shm")
        backup_file = self.mock_app_home / "test.backup"
        wal_file.write_text("wal data")
        shm_file.write_text("shm data")
        backup_file.write_text("backup data")

        self.assertTrue(wal_file.exists())
        self.assertTrue(shm_file.exists())
        self.assertTrue(backup_file.exists())

        # Reset vault and wipe all
        self.service.reset_vault_and_wipe_all()

        # Check all targets are removed
        self.assertFalse(self.mock_meta.exists())
        self.assertFalse(self.mock_secret.exists())
        self.assertFalse(self.mock_db.exists())
        self.assertFalse(wal_file.exists())
        self.assertFalse(shm_file.exists())
        self.assertFalse(backup_file.exists())

        # Check service is uninitialized and session is cleared
        self.assertFalse(self.service.is_initialized())
        self.assertFalse(self.service.is_unlocked())

        # Setting up master password anew succeeds
        self.service.setup_master_password("NewMasterPwd456!", "NewMasterPwd456!")
        self.assertTrue(self.service.is_initialized())
        self.assertTrue(self.mock_meta.exists())

        # Authenticating with new master password succeeds and secrets are empty
        auth_ok, _ = self.service.authenticate("NewMasterPwd456!")
        self.assertTrue(auth_ok)
        self.assertEqual(len(self.service.get_secret_names()), 0)

    def test_lockout_and_failed_attempts_persist_across_restarts(self):
        # 1st failed attempt
        self.service.authenticate("WrongPassword1")
        status = self.service.get_lockout_status()
        self.assertEqual(status["failed_attempts"], 1)
        self.assertFalse(status["is_locked_out"])

        # Simulate process restart by instantiating new service and initializing
        service_session_2 = SecretManagerService(client_name="test_session_2")
        service_session_2.initialize()
        status_session_2 = service_session_2.get_lockout_status()
        self.assertEqual(status_session_2["failed_attempts"], 1)

        # 2nd failed attempt in session 2
        service_session_2.authenticate("WrongPassword2")
        self.assertEqual(service_session_2.get_lockout_status()["failed_attempts"], 2)

        # Simulate another process restart
        service_session_3 = SecretManagerService(client_name="test_session_3")
        service_session_3.initialize()
        self.assertEqual(service_session_3.get_lockout_status()["failed_attempts"], 2)

        # 3rd failed attempt triggers lockout
        ok, msg = service_session_3.authenticate("WrongPassword3")
        self.assertFalse(ok)
        status_3 = service_session_3.get_lockout_status()
        self.assertEqual(status_3["failed_attempts"], 3)
        self.assertTrue(status_3["is_locked_out"])
        self.assertGreater(status_3["remaining_seconds"], 0)

        # Simulate process restart during active lockout
        service_session_4 = SecretManagerService(client_name="test_session_4")
        service_session_4.initialize()
        status_4 = service_session_4.get_lockout_status()
        self.assertEqual(status_4["failed_attempts"], 3)
        self.assertTrue(status_4["is_locked_out"])
        self.assertGreater(status_4["remaining_seconds"], 0)

        # Attempting authentication during lockout is blocked
        blocked_ok, blocked_msg = service_session_4.authenticate(self.master_pwd)
        self.assertFalse(blocked_ok)
        self.assertIn("Too many failed attempts", blocked_msg)

    def test_exponential_backoff_scales_and_persists_indefinitely(self):
        # Perform 3 failures to reach threshold
        for _ in range(FAILED_AUTH_LOCKOUT_THRESHOLD):
            self.service.authenticate("Wrong")

        # Exponent 0: base seconds
        status = self.service.get_lockout_status()
        self.assertEqual(status["failed_attempts"], 3)
        self.assertLessEqual(status["remaining_seconds"], FAILED_AUTH_LOCKOUT_BASE_SECONDS + 2)

        # Expire lockout artificially
        meta = self.service._require_metadata()
        meta._lockout_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.service._persist_metadata()

        # Simulate restart
        s2 = SecretManagerService()
        s2.initialize()
        # 4th failure -> exponent 1 (base * 2)
        s2.authenticate("WrongAgain")
        status_s2 = s2.get_lockout_status()
        self.assertEqual(status_s2["failed_attempts"], 4)
        self.assertGreater(status_s2["remaining_seconds"], FAILED_AUTH_LOCKOUT_BASE_SECONDS)
        # Allow small timing buffer (+2s) for CI runner clock rounding
        self.assertLessEqual(status_s2["remaining_seconds"], FAILED_AUTH_LOCKOUT_BASE_SECONDS * 2 + 2)


if __name__ == "__main__":
    unittest.main()
