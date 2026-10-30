import unittest
from datetime import datetime

from dev.abhishekraha.secretmanager.model.Secret import Secret


class SecretModelTests(unittest.TestCase):
    def test_default_values(self):
        secret = Secret("github", "user1", "pass1")
        self.assertEqual("github", secret.get_name())
        self.assertEqual("user1", secret.get_username())
        self.assertEqual("pass1", secret.get_password())
        self.assertEqual("", secret.get_url())
        self.assertEqual("", secret.get_comments())
        self.assertEqual([], secret.get_tags())
        self.assertEqual("login", secret.get_category())
        self.assertFalse(secret.is_favorite())
        self.assertFalse(secret.get_favorite())
        self.assertEqual("", secret.get_totp_secret())
        self.assertIsInstance(secret.get_create_date(), datetime)
        self.assertIsNone(secret.get_update_date())

    def test_custom_values_and_mutators(self):
        secret = Secret(
            name="bank",
            username="alice",
            password="secretpassword",
            url="https://bank.example.com",
            comments="primary account",
            tags=["finance", "important"],
            category="card",
            favorite=True,
            totp_secret="JBSWY3DPEHPK3PXP",
        )
        self.assertEqual(["finance", "important"], secret.get_tags())
        self.assertEqual("card", secret.get_category())
        self.assertTrue(secret.is_favorite())
        self.assertEqual("JBSWY3DPEHPK3PXP", secret.get_totp_secret())

        # Test setters
        secret.set_tags(["banking"])
        self.assertEqual(["banking"], secret.get_tags())
        secret.set_category("login")
        self.assertEqual("login", secret.get_category())
        secret.set_favorite(False)
        self.assertFalse(secret.is_favorite())
        secret.set_totp_secret("NBSWY3DP")
        self.assertEqual("NBSWY3DP", secret.get_totp_secret())

    def test_to_dict_and_from_dict_round_trip(self):
        secret = Secret(
            name="aws",
            username="admin",
            password="masterkey12345",
            url="https://aws.amazon.com",
            comments="root account",
            tags=["cloud", "work"],
            category="login",
            favorite=True,
            totp_secret="JBSWY3DPEHPK3PXP",
        )
        payload = secret.to_dict()

        self.assertEqual("aws", payload["name"])
        self.assertEqual("admin", payload["username"])
        self.assertEqual(["cloud", "work"], payload["tags"])
        self.assertEqual("login", payload["category"])
        self.assertTrue(payload["favorite"])
        self.assertEqual("JBSWY3DPEHPK3PXP", payload["totp_secret"])

        restored = Secret.from_dict(payload)
        self.assertEqual(secret.get_name(), restored.get_name())
        self.assertEqual(secret.get_username(), restored.get_username())
        self.assertEqual(secret.get_tags(), restored.get_tags())
        self.assertEqual(secret.get_category(), restored.get_category())
        self.assertEqual(secret.is_favorite(), restored.is_favorite())
        self.assertEqual(secret.get_totp_secret(), restored.get_totp_secret())

    def test_backward_compatibility_deserialization(self):
        # Legacy payload without new fields (tags, category, favorite, totp_secret)
        legacy_payload = {
            "name": "legacy_service",
            "username": "legacy_user",
            "password": "old_password_123",
            "url": "https://legacy.example.com",
            "comments": "old comments",
            "created_at": "2025-01-01T12:00:00",
            "updated_at": None,
        }

        secret = Secret.from_dict(legacy_payload)
        self.assertEqual("legacy_service", secret.get_name())
        self.assertEqual([], secret.get_tags())
        self.assertEqual("login", secret.get_category())
        self.assertFalse(secret.is_favorite())
        self.assertEqual("", secret.get_totp_secret())


if __name__ == "__main__":
    unittest.main()
