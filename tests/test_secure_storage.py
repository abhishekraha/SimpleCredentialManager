import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from dev.abhishekraha.secretmanager.codec import CodecUtils, SerDeUtils
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import FAILED_AUTH_LOCKOUT_BASE_SECONDS
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager
from dev.abhishekraha.secretmanager.utils.AuditLogger import log_event


class SecureStorageTests(unittest.TestCase):
    def tearDown(self):
        CodecUtils.clear_derived_key()

    def test_metadata_round_trip_validates_master_password(self):
        with TemporaryDirectory() as temp_dir:
            metadata_file = Path(temp_dir) / "metadata.json"
            metadata = SecretManagerMetaDataManager()
            metadata.set_master_password("correct horse battery staple")

            SerDeUtils.dump(metadata, metadata_file)
            loaded_metadata = SerDeUtils.load(metadata_file)

            self.assertTrue(loaded_metadata.validate_master_password("correct horse battery staple"))
            self.assertFalse(loaded_metadata.validate_master_password("wrong password"))

    def test_legacy_metadata_versions_are_rejected(self):
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("correct horse battery staple")
        legacy_payload = metadata.to_dict()
        legacy_payload["version"] = 3

        with self.assertRaisesRegex(ValueError, "Unsupported metadata version"):
            SecretManagerMetaDataManager.from_dict(legacy_payload)

    def test_vault_file_is_encrypted_and_round_trips(self):
        with TemporaryDirectory() as temp_dir:
            metadata = SecretManagerMetaDataManager()
            metadata.set_master_password("correct horse battery staple")
            self.assertTrue(metadata.validate_master_password("correct horse battery staple"))

            vault_file = Path(temp_dir) / "vault.bin"
            secrets = {
                "email": Secret("email", "alice", "s3cr3t!", "https://example.com", "primary mailbox")
            }

            SerDeUtils.dump_secrets(secrets, vault_file)

            vault_bytes = vault_file.read_bytes()
            self.assertNotIn(b"email", vault_bytes)
            self.assertNotIn(b"alice", vault_bytes)
            self.assertNotIn(b"s3cr3t!", vault_bytes)

            loaded_secrets = SerDeUtils.load_secrets(vault_file)
            self.assertEqual("alice", loaded_secrets["email"].get_username())
            self.assertEqual("s3cr3t!", loaded_secrets["email"].get_password())

    def test_failed_auth_attempts_trigger_lockout_and_reset(self):
        metadata = SecretManagerMetaDataManager()
        base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

        self.assertEqual(0, metadata.record_failed_auth_attempt(base_time))
        self.assertEqual(0, metadata.record_failed_auth_attempt(base_time))

        lockout_seconds = metadata.record_failed_auth_attempt(base_time)
        self.assertEqual(FAILED_AUTH_LOCKOUT_BASE_SECONDS, lockout_seconds)
        self.assertTrue(metadata.is_locked_out(base_time))
        self.assertGreaterEqual(metadata.get_lockout_remaining_seconds(base_time), lockout_seconds)

        after_lockout = base_time + timedelta(seconds=lockout_seconds + 1)
        self.assertFalse(metadata.is_locked_out(after_lockout))
        self.assertTrue(metadata.clear_expired_lockout(after_lockout))

        metadata.reset_failed_auth_attempts()
        self.assertEqual(0, metadata.get_failed_auth_attempts())
        self.assertEqual(0, metadata.get_lockout_remaining_seconds(after_lockout))

    def test_audit_log_writes_json_lines(self):
        with TemporaryDirectory() as temp_dir:
            audit_log_file = Path(temp_dir) / "audit.log"

            log_event(
                "authentication_failed",
                log_file=audit_log_file,
                failed_attempts=2,
                attempts_before_lockout=1,
            )

            audit_record = json.loads(audit_log_file.read_text(encoding="utf-8").strip())
            self.assertEqual("authentication_failed", audit_record["event"])
            self.assertEqual(2, audit_record["failed_attempts"])
            self.assertEqual(1, audit_record["attempts_before_lockout"])
            self.assertIn("timestamp", audit_record)


if __name__ == "__main__":
    unittest.main()
