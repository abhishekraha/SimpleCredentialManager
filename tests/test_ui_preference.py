import os
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from dev.abhishekraha.secretmanager.codec import SerDeUtils
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager
from dev.abhishekraha.secretmanager.storage.SqliteVaultStorage import SqliteVaultStorage


class UiPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "vault.scmdb"
        self.metadata_path = self.temp_path / "metadata.json"
        self.storage = SqliteVaultStorage(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sqlite_storage_default_preference(self):
        # When DB does not exist, default should be 'modern'
        self.assertEqual("modern", self.storage.get_ui_preference())

        # When initialized without preferred_ui, default should be 'modern'
        self.storage.init_vault(
            salt=b"test_salt",
            wrapped_dek=b"test_dek",
        )
        self.assertEqual("modern", self.storage.get_ui_preference())

    def test_sqlite_storage_set_and_get_preference(self):
        self.storage.init_vault(
            salt=b"test_salt",
            wrapped_dek=b"test_dek",
        )
        self.storage.set_ui_preference("classic")
        self.assertEqual("classic", self.storage.get_ui_preference())

        self.storage.set_ui_preference("modern")
        self.assertEqual("modern", self.storage.get_ui_preference())

    def test_sqlite_storage_invalid_preference_raises(self):
        self.storage.init_db()
        with self.assertRaises(ValueError):
            self.storage.set_ui_preference("invalid_ui")

    def test_metadata_manager_preferred_ui_roundtrip(self):
        meta = SecretManagerMetaDataManager()
        meta.set_master_password("masterkey123")
        self.assertEqual("modern", meta.get_preferred_ui())

        meta.set_preferred_ui("classic")
        self.assertEqual("classic", meta.get_preferred_ui())

        payload = meta.to_dict()
        self.assertEqual("classic", payload.get("preferred_ui"))

        # Deserialization test
        meta2 = SecretManagerMetaDataManager.from_dict(payload)
        self.assertEqual("classic", meta2.get_preferred_ui())

    def test_metadata_manager_invalid_preference_raises(self):
        meta = SecretManagerMetaDataManager()
        with self.assertRaises(ValueError):
            meta.set_preferred_ui("unknown")

    def test_service_get_and_set_ui_preference(self):
        with patch("dev.abhishekraha.secretmanager.core.SecretManagerService.VAULT_DB_FILE", self.db_path), \
             patch("dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_MANAGER_META_DATA", self.metadata_path):

            service = SecretManagerService(client_name="TestClient")

            # Default before setup
            self.assertEqual("modern", service.get_ui_preference())

            # Change to classic
            service.set_ui_preference("classic")
            self.assertEqual("classic", service.get_ui_preference())

            # Verify saved in SQLite storage directly
            storage = SqliteVaultStorage(self.db_path)
            self.assertEqual("classic", storage.get_ui_preference())

            # Change back to modern
            service.set_ui_preference("modern")
            self.assertEqual("modern", service.get_ui_preference())
            self.assertEqual("modern", storage.get_ui_preference())

    def test_service_invalid_ui_preference_raises(self):
        service = SecretManagerService(client_name="TestClient")
        with self.assertRaises(ValueError):
            service.set_ui_preference("fancy_ui")


if __name__ == "__main__":
    unittest.main()
