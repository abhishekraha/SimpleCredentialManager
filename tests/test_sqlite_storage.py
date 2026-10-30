import os
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet

from dev.abhishekraha.secretmanager.codec import CodecUtils
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.storage.SqliteVaultStorage import (
    SqliteVaultStorage,
    compute_blind_index,
)


class SqliteVaultStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "vault.scmdb"
        self.storage = SqliteVaultStorage(self.db_path)
        self.dek = Fernet.generate_key()
        self.blind_key = CodecUtils.derive_blind_index_key(self.dek)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db_and_wal_mode(self):
        self.storage.init_db()
        self.assertTrue(self.db_path.exists())

        with self.storage._get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            self.assertEqual("wal", mode.lower())

    def test_init_vault_and_get_vault_meta(self):
        salt = os.urandom(16)
        wrapped_dek = b"test_wrapped_dek_bytes"
        kdf_params = {"memory": 65536, "iterations": 3}
        lockout_data = {"failed_attempts": 0}

        self.storage.init_vault(
            salt=salt,
            wrapped_dek=wrapped_dek,
            kdf_params=kdf_params,
            kdf_algorithm="argon2id",
            version=5,
            lockout_data=lockout_data,
        )

        meta = self.storage.get_vault_meta()
        self.assertIsNotNone(meta)
        self.assertEqual(5, meta["version"])
        self.assertEqual(salt, meta["salt"])
        self.assertEqual("argon2id", meta["kdf_algorithm"])
        self.assertEqual(wrapped_dek, meta["wrapped_dek"])
        self.assertEqual(kdf_params, meta["kdf_params"])
        self.assertEqual(lockout_data, meta["lockout_data"])
        self.assertIn("created_at", meta)

    def test_save_and_get_secret(self):
        secret = Secret(
            name="GitHub",
            username="octocat",
            password="SuperSecurePassword123!",
            url="https://github.com",
            comments="Developer account",
            category="development",
            is_favorite=True,
            totp_secret="JBSWY3DPEHPK3PXP",
            tags=["code", "git"],
        )

        self.storage.save_secret(secret, self.dek, self.blind_key)

        retrieved = self.storage.get_secret("GitHub", self.dek, self.blind_key)
        self.assertIsNotNone(retrieved)
        self.assertEqual("GitHub", retrieved.get_name())
        self.assertEqual("octocat", retrieved.get_username())
        self.assertEqual("SuperSecurePassword123!", retrieved.get_password())
        self.assertEqual("https://github.com", retrieved.get_url())
        self.assertEqual("Developer account", retrieved.get_comments())
        self.assertEqual("development", retrieved.get_category())
        self.assertTrue(retrieved.is_favorite())
        self.assertEqual("JBSWY3DPEHPK3PXP", retrieved.get_totp_secret())
        self.assertEqual(["code", "git"], retrieved.get_tags())

    def test_case_insensitive_lookup_via_blind_index(self):
        secret = Secret("AWS Console", "admin", "cloudpass123")
        self.storage.save_secret(secret, self.dek, self.blind_key)

        # Lookup with lowercase and uppercase
        self.assertIsNotNone(self.storage.get_secret("aws console", self.dek, self.blind_key))
        self.assertIsNotNone(self.storage.get_secret("AWS CONSOLE", self.dek, self.blind_key))
        self.assertIsNone(self.storage.get_secret("nonexistent", self.dek, self.blind_key))

    def test_lazy_list_secrets_does_not_decrypt_passwords(self):
        secret1 = Secret("Alpha", "user_a", "super_secret_a", category="work", is_favorite=True)
        secret2 = Secret("Beta", "user_b", "super_secret_b", category="personal", is_favorite=False)

        self.storage.save_secret(secret1, self.dek, self.blind_key)
        self.storage.save_secret(secret2, self.dek, self.blind_key)

        headers = self.storage.list_secrets(self.dek)
        self.assertEqual(2, len(headers))
        self.assertEqual("Alpha", headers[0]["name"])
        self.assertEqual("user_a", headers[0]["username"])
        self.assertEqual("Beta", headers[1]["name"])
        self.assertEqual("user_b", headers[1]["username"])
        # Passwords must not be exposed in the list headers
        for h in headers:
            self.assertNotIn("password", h)

    def test_list_secrets_with_category_filter(self):
        secret1 = Secret("ServiceA", "u1", "p1", category="finance")
        secret2 = Secret("ServiceB", "u2", "p2", category="social")
        self.storage.save_secret(secret1, self.dek, self.blind_key)
        self.storage.save_secret(secret2, self.dek, self.blind_key)

        finance_items = self.storage.list_secrets(self.dek, category="finance")
        self.assertEqual(1, len(finance_items))
        self.assertEqual("ServiceA", finance_items[0]["name"])

    def test_update_existing_secret(self):
        secret = Secret("MySecret", "user", "pass1")
        self.storage.save_secret(secret, self.dek, self.blind_key)

        updated_secret = Secret("MySecret", "user_updated", "pass2", comments="updated comments")
        self.storage.save_secret(updated_secret, self.dek, self.blind_key)

        self.assertEqual(1, self.storage.count_secrets())
        retrieved = self.storage.get_secret("MySecret", self.dek, self.blind_key)
        self.assertEqual("user_updated", retrieved.get_username())
        self.assertEqual("pass2", retrieved.get_password())
        self.assertEqual("updated comments", retrieved.get_comments())

    def test_delete_secret(self):
        secret = Secret("ToDelete", "user", "pass")
        self.storage.save_secret(secret, self.dek, self.blind_key)
        self.assertEqual(1, self.storage.count_secrets())

        deleted = self.storage.delete_secret("ToDelete", self.blind_key)
        self.assertTrue(deleted)
        self.assertEqual(0, self.storage.count_secrets())
        self.assertIsNone(self.storage.get_secret("ToDelete", self.dek, self.blind_key))

        # Deleting non-existent returns False
        self.assertFalse(self.storage.delete_secret("NonExistent", self.blind_key))

    def test_get_all_secrets(self):
        s1 = Secret("Sec1", "u1", "p1")
        s2 = Secret("Sec2", "u2", "p2")
        self.storage.save_secret(s1, self.dek, self.blind_key)
        self.storage.save_secret(s2, self.dek, self.blind_key)

        all_sec = self.storage.get_all_secrets(self.dek)
        self.assertEqual(2, len(all_sec))
        self.assertIn("Sec1", all_sec)
        self.assertIn("Sec2", all_sec)
        self.assertEqual("p1", all_sec["Sec1"].get_password())
        self.assertEqual("p2", all_sec["Sec2"].get_password())

    def test_update_vault_meta(self):
        self.storage.init_vault(
            salt=b"orig_salt",
            wrapped_dek=b"orig_dek",
            lockout_data={"failed_attempts": 1},
        )
        self.storage.update_vault_meta(
            wrapped_dek=b"new_dek",
            lockout_data={"failed_attempts": 2},
        )
        meta = self.storage.get_vault_meta()
        self.assertEqual(b"new_dek", meta["wrapped_dek"])
        self.assertEqual({"failed_attempts": 2}, meta["lockout_data"])


if __name__ == "__main__":
    unittest.main()
