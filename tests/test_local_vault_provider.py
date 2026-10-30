import unittest
from unittest.mock import MagicMock, patch
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.providers.LocalVaultProvider import LocalVaultProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret


class TestLocalVaultProvider(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.provider = LocalVaultProvider(service=self.mock_service)

    def test_implements_interface(self):
        self.assertIsInstance(self.provider, VaultDataProvider)

    def test_delegates_lifecycle_and_auth(self):
        self.mock_service.initialize.return_value = True
        self.mock_service.is_initialized.return_value = True
        self.mock_service.is_unlocked.return_value = False
        self.mock_service.authenticate.return_value = (True, "Unlocked successfully")
        self.mock_service.get_lockout_status.return_value = {"locked": False, "remaining_seconds": 0}

        self.assertTrue(self.provider.initialize())
        self.mock_service.initialize.assert_called_once()

        self.assertTrue(self.provider.is_initialized())
        self.assertFalse(self.provider.is_unlocked())

        ok, msg = self.provider.authenticate("MasterPass123!")
        self.assertTrue(ok)
        self.assertEqual(msg, "Unlocked successfully")
        self.mock_service.authenticate.assert_called_once_with("MasterPass123!")

        self.assertEqual(self.provider.get_lockout_status(), {"locked": False, "remaining_seconds": 0})
        self.mock_service.get_lockout_status.assert_called_once()

        self.provider.setup_master_password("pass1", "pass1")
        self.mock_service.setup_master_password.assert_called_once_with("pass1", "pass1")

        self.provider.change_master_password("curr", "new", "new")
        self.mock_service.change_master_password.assert_called_once_with("curr", "new", "new")

        self.provider.lock_vault()
        self.mock_service.lock_vault.assert_called_once()

    def test_delegates_secret_crud(self):
        dummy_secret = Secret(name="github", username="user", password="pwd")
        self.mock_service.get_secret_records.return_value = [dummy_secret]
        records = self.provider.get_secret_records(filter_text="git")
        self.assertEqual(records, [dummy_secret])
        self.mock_service.get_secret_records.assert_called_once_with("git")

        self.mock_service.get_secret_names.return_value = ["github"]
        names = self.provider.get_secret_names(filter_text="git")
        self.assertEqual(names, ["github"])
        self.mock_service.get_secret_names.assert_called_once_with("git")

        self.mock_service.get_secret.return_value = dummy_secret
        secret = self.provider.get_secret("github")
        self.assertEqual(secret, dummy_secret)
        self.mock_service.get_secret.assert_called_once_with("github")

        self.provider.add_secret(
            name="github",
            username="user",
            password="pwd",
            url="https://github.com",
            comments="dev key",
            category="login",
            is_favorite=True,
            totp_secret="JBSWY3DPEHPK3PXP",
            tags=["dev", "git"],
        )
        self.mock_service.add_secret.assert_called_once_with(
            name="github",
            username="user",
            password="pwd",
            url="https://github.com",
            comments="dev key",
            category="login",
            is_favorite=True,
            totp_secret="JBSWY3DPEHPK3PXP",
            tags=["dev", "git"],
        )

        self.provider.update_secret(
            original_name="github",
            new_name="github-work",
            username="user2",
            password="pwd2",
            url="https://github.com/work",
            comments="updated",
            category="server",
            is_favorite=False,
            totp_secret=None,
            tags=["work"],
        )
        self.mock_service.update_secret.assert_called_once_with(
            original_name="github",
            new_name="github-work",
            username="user2",
            password="pwd2",
            url="https://github.com/work",
            comments="updated",
            category="server",
            is_favorite=False,
            totp_secret=None,
            tags=["work"],
        )

        self.provider.delete_secret("github")
        self.mock_service.delete_secret.assert_called_once_with("github")

        self.mock_service.generate_password.return_value = "generated_pwd"
        gen = self.provider.generate_password(24)
        self.assertEqual(gen, "generated_pwd")
        self.mock_service.generate_password.assert_called_once_with(24)

    @patch("dev.abhishekraha.secretmanager.providers.LocalVaultProvider.PasswordHealthService")
    def test_audit_health_delegation(self, mock_health_service_cls):
        mock_health_instance = MagicMock()
        mock_health_service_cls.return_value = mock_health_instance
        mock_health_instance.audit_vault.return_value = {"score": 95, "weak_count": 0}

        dummy_secret = Secret(name="github", username="user", password="pwd")
        self.mock_service.get_secret_records.return_value = [dummy_secret]

        result = self.provider.audit_health()
        self.assertEqual(result, {"score": 95, "weak_count": 0})
        self.mock_service.get_secret_records.assert_called_once_with("")
        mock_health_instance.audit_vault.assert_called_once_with([dummy_secret])

    @patch("dev.abhishekraha.secretmanager.providers.LocalVaultProvider.SecretManagerService")
    def test_default_service_instantiation(self, mock_service_cls):
        provider = LocalVaultProvider()
        mock_service_cls.assert_called_once_with(client_name="desktop-local-provider")
        self.assertIsNotNone(provider.service)


if __name__ == "__main__":
    unittest.main()
