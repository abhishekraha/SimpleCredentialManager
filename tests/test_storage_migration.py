import json
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dev.abhishekraha.secretmanager.codec import CodecUtils, SerDeUtils
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import (
    SecretManagerMetaDataManager,
)
from dev.abhishekraha.secretmanager.storage.SqliteVaultStorage import SqliteVaultStorage
from dev.abhishekraha.secretmanager.storage.StorageMigrator import StorageMigrator


class StorageMigratorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.legacy_meta = self.root / ".simpleCredentialManager.metadata"
        self.legacy_secret = self.root / ".simpleCredentialManager.secret"
        self.target_db = self.root / "vault.scmdb"

        self.migrator = StorageMigrator(
            legacy_secret_file=self.legacy_secret,
            legacy_meta_file=self.legacy_meta,
            target_db_file=self.target_db,
        )

    def tearDown(self):
        CodecUtils.clear_derived_key()
        self.temp_dir.cleanup()

    def test_is_migration_needed_true_when_legacy_exists_and_db_does_not(self):
        self.assertFalse(self.migrator.is_migration_needed())

        self.legacy_meta.write_text("{}", encoding="utf-8")
        self.assertTrue(self.migrator.is_migration_needed())

        self.target_db.write_text("", encoding="utf-8")
        self.assertFalse(self.migrator.is_migration_needed())

    def test_migrate_successfully_transfers_secrets_and_creates_backups(self):
        master_password = "SuperSecretMasterPassword123!"

        # Create legacy metadata and secrets
        meta = SecretManagerMetaDataManager()
        meta.set_master_password(master_password)
        SerDeUtils.dump(meta, self.legacy_meta)

        CodecUtils.derive_key(master_password, meta.get_salt())
        secrets = {
            "WorkEmail": Secret(
                "WorkEmail", "alice@corp.com", "pass_corp_1", "https://mail.corp.com", "primary email"
            ),
            "PersonalGitHub": Secret(
                "PersonalGitHub", "alice-dev", "gh_token_xyz", "https://github.com", "dev key"
            ),
        }
        SerDeUtils.dump_secrets(secrets, self.legacy_secret)
        CodecUtils.clear_derived_key()

        self.assertTrue(self.migrator.is_migration_needed())

        # Perform migration
        result = self.migrator.migrate(master_password)

        self.assertTrue(result["migrated"])
        self.assertEqual(2, result["count"])
        self.assertTrue(self.target_db.exists())

        # Legacy files should have been renamed to .backup
        meta_backup = self.legacy_meta.with_suffix(".metadata.backup")
        secret_backup = self.legacy_secret.with_suffix(".secret.backup")
        self.assertTrue(meta_backup.exists())
        self.assertTrue(secret_backup.exists())
        self.assertFalse(self.legacy_meta.exists())
        self.assertFalse(self.legacy_secret.exists())

        # Verify new SQLite database contents
        storage = SqliteVaultStorage(self.target_db)
        dek = CodecUtils.get_derived_key()
        blind_key = CodecUtils.derive_blind_index_key(dek)

        migrated_meta = storage.get_vault_meta()
        self.assertIsNotNone(migrated_meta)
        self.assertEqual(meta.get_salt(), migrated_meta["salt"])

        # Check full secret retrieval
        s1 = storage.get_secret("WorkEmail", dek, blind_key)
        self.assertIsNotNone(s1)
        self.assertEqual("alice@corp.com", s1.get_username())
        self.assertEqual("pass_corp_1", s1.get_password())
        self.assertEqual("primary email", s1.get_comments())

        s2 = storage.get_secret("PersonalGitHub", dek, blind_key)
        self.assertIsNotNone(s2)
        self.assertEqual("gh_token_xyz", s2.get_password())

        # Check list_secrets lazy loading
        listed = storage.list_secrets(dek)
        self.assertEqual(2, len(listed))
        names = {item["name"] for item in listed}
        self.assertEqual({"WorkEmail", "PersonalGitHub"}, names)

    def test_migrate_fails_with_invalid_master_password(self):
        meta = SecretManagerMetaDataManager()
        meta.set_master_password("correct_password")
        SerDeUtils.dump(meta, self.legacy_meta)
        CodecUtils.derive_key("correct_password", meta.get_salt())
        SerDeUtils.dump_secrets({}, self.legacy_secret)
        CodecUtils.clear_derived_key()

        with self.assertRaises(ValueError):
            self.migrator.migrate("wrong_password")

        # Database should not exist, legacy files should remain intact
        self.assertFalse(self.target_db.exists())
        self.assertTrue(self.legacy_meta.exists())
        self.assertTrue(self.legacy_secret.exists())


if __name__ == "__main__":
    unittest.main()
