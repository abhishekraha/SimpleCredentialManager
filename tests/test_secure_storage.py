import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dev.abhishekraha.secretmanager.codec import CodecUtils, SerDeUtils
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager


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


if __name__ == "__main__":
    unittest.main()
