import unittest
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from dev.abhishekraha.secretmanager.codec import CodecUtils, SerDeUtils
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager


class ChangeMasterPasswordTests(unittest.TestCase):
    def setUp(self):
        """Create fresh temp directory for each test and set up patches."""
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        # Create patches for configuration
        self.patcher1 = patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.SECRET_MANAGER_META_DATA",
                             self.temp_path / "metadata.json")
        self.patcher2 = patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.SECRET_FILE",
                             self.temp_path / "vault.bin")
        self.patcher1.start()
        self.patcher2.start()

    def tearDown(self):
        """Clean up patches and temp directory."""
        self.patcher1.stop()
        self.patcher2.stop()
        CodecUtils.clear_derived_key()
        self.temp_dir.cleanup()

    def _create_service(self):
        """Create a SecretManagerService with mocked paths."""
        service = SecretManagerService(client_name="test")
        # Mock is_initialized to return False so setup can proceed
        service.is_initialized = lambda: False
        return service

    def test_change_master_password_with_valid_inputs(self):
        """Test successful master password change with valid current and new passwords."""
        service = self._create_service()

        # Setup initial vault
        service.setup_master_password("old_password", "old_password")
        # Re-authenticate since setup clears the key
        service.authenticate("old_password")

        # Add a test secret
        service.add_secret("test_secret", "username", "password", "https://example.com", "comments")

        # Retrieve and verify the secret before password change
        secret_before = service.get_secret("test_secret")
        self.assertIsNotNone(secret_before)
        self.assertEqual("username", secret_before.get_username())
        self.assertEqual("password", secret_before.get_password())

        # Change master password
        service.change_master_password("old_password", "new_password", "new_password")

        # Lock and re-authenticate with new password
        service.lock_vault()
        success, message = service.authenticate("new_password")

        self.assertTrue(success)
        self.assertEqual("Authentication succeeded.", message)

        # Verify secret is still accessible with new password
        secret_after = service.get_secret("test_secret")
        self.assertIsNotNone(secret_after)
        self.assertEqual("username", secret_after.get_username())
        self.assertEqual("password", secret_after.get_password())

    def test_change_master_password_with_empty_current_password(self):
        """Test that empty current password raises ValueError."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("old_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_audit"):
            with self.assertRaisesRegex(ValueError, "Current master password cannot be empty"):
                service.change_master_password("", "new_password", "new_password")

    def test_change_master_password_with_empty_new_password(self):
        """Test that empty new password raises ValueError."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("old_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_audit"):
            with self.assertRaisesRegex(ValueError, "New master password cannot be empty"):
                service.change_master_password("old_password", "", "")

    def test_change_master_password_with_mismatched_confirmation(self):
        """Test that mismatched new password and confirmation raises ValueError."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("old_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_audit"):
            with self.assertRaisesRegex(ValueError, "New password and confirmation do not match"):
                service.change_master_password("old_password", "new_password", "different_password")

    def test_change_master_password_same_as_old(self):
        """Test that new password cannot be the same as old password."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("same_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_audit"):
            with self.assertRaisesRegex(ValueError, "New password must be different from the current password"):
                service.change_master_password("same_password", "same_password", "same_password")

    def test_change_master_password_with_invalid_current_password(self):
        """Test that invalid current password raises ValueError."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("correct_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_audit"):
            with self.assertRaisesRegex(ValueError, "Current master password is invalid"):
                service.change_master_password("wrong_password", "new_password", "new_password")

    def test_change_master_password_old_password_no_longer_works(self):
        """Test that old password cannot authenticate after password change."""
        service = self._create_service()

        # Setup initial vault
        service.setup_master_password("old_password", "old_password")

        # Change master password
        service.change_master_password("old_password", "new_password", "new_password")

        # Lock vault
        service.lock_vault()

        # Try to authenticate with old password
        success, message = service.authenticate("old_password")

        self.assertFalse(success)
        self.assertIn("invalid", message.lower())

    def test_change_master_password_re_encrypts_secrets(self):
        """Test that secrets are properly re-encrypted with new key."""
        service = self._create_service()

        # Setup initial vault
        service.setup_master_password("old_password", "old_password")
        # Re-authenticate since setup clears the key
        service.authenticate("old_password")

        # Add multiple secrets
        service.add_secret("secret1", "user1", "pass1", "url1", "comment1")
        service.add_secret("secret2", "user2", "pass2", "url2", "comment2")
        service.add_secret("secret3", "user3", "pass3", "url3", "comment3")

        # Get vault file before password change - may not exist if using in-memory temp storage
        vault_file = Path(self.temp_path) / "vault.bin"
        if vault_file.exists():
            vault_bytes_before = vault_file.read_bytes()
        else:
            vault_bytes_before = None

        # Change master password
        service.change_master_password("old_password", "new_password", "new_password")

        # Get vault file after password change
        if vault_file.exists():
            vault_bytes_after = vault_file.read_bytes()
            # Only compare if we had the before bytes
            if vault_bytes_before is not None:
                # Vault file should be different (re-encrypted with new key)
                self.assertNotEqual(vault_bytes_before, vault_bytes_after)

        # Lock and authenticate with new password
        service.lock_vault()
        success, _ = service.authenticate("new_password")
        self.assertTrue(success)

        # Verify all secrets are still accessible
        secret1 = service.get_secret("secret1")
        secret2 = service.get_secret("secret2")
        secret3 = service.get_secret("secret3")

        self.assertEqual("user1", secret1.get_username())
        self.assertEqual("pass1", secret1.get_password())
        self.assertEqual("user2", secret2.get_username())
        self.assertEqual("pass2", secret2.get_password())
        self.assertEqual("user3", secret3.get_username())
        self.assertEqual("pass3", secret3.get_password())

    def test_change_master_password_updates_metadata_verifier(self):
        """Test that metadata password verifier is updated correctly."""
        service = self._create_service()

        # Setup initial vault
        service.setup_master_password("old_password", "old_password")

        # Get original password verifier
        old_metadata = service._metadata_manager
        old_verifier = old_metadata._password_verifier

        # Change master password
        service.change_master_password("old_password", "new_password", "new_password")

        # Get updated password verifier
        new_metadata = service._metadata_manager
        new_verifier = new_metadata._password_verifier

        # Verifiers should be different
        self.assertNotEqual(old_verifier, new_verifier)

        # New verifier should validate with new password
        self.assertTrue(new_metadata.validate_master_password("new_password"))

        # New verifier should not validate with old password
        self.assertFalse(new_metadata.validate_master_password("old_password"))

    def test_change_master_password_audit_logging_success(self):
        """Test that successful password change is audited."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("old_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_persist_metadata"):
            with patch.object(service, "_persist_secrets"):
                with patch.object(service, "_audit") as mock_audit:
                    service.change_master_password("old_password", "new_password", "new_password")

                    # Verify audit was called with success
                    mock_audit.assert_called_with("master_password_changed")

    def test_change_master_password_audit_logging_failure_invalid_password(self):
        """Test that failed password change attempts are audited."""
        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password("correct_password")

        service = self._create_service()
        service._metadata_manager = metadata

        with patch.object(service, "_audit") as mock_audit:
            try:
                service.change_master_password("wrong_password", "new_password", "new_password")
            except ValueError:
                pass

            # Verify audit was called with failure reason
            audit_calls = [call for call in mock_audit.call_args_list
                          if call[0][0] == "master_password_change_failed"]
            self.assertTrue(any("invalid_current_password" in str(call) for call in audit_calls))

    def test_change_master_password_with_special_characters(self):
        """Test master password change with special characters in passwords."""
        service = self._create_service()

        # Setup with special characters
        old_pass = "p@$$w0rd!#%&*"
        new_pass = "N3w_P@$$!@#$%^&*()"

        service.setup_master_password(old_pass, old_pass)
        service.change_master_password(old_pass, new_pass, new_pass)

        service.lock_vault()
        success, _ = service.authenticate(new_pass)

        self.assertTrue(success)

    def test_change_master_password_with_unicode_characters(self):
        """Test master password change with unicode characters."""
        service = self._create_service()

        # Setup with unicode characters
        old_pass = "パスワード123"  # Japanese: password
        new_pass = "新しいパスワード456"  # Japanese: new password

        service.setup_master_password(old_pass, old_pass)
        service.change_master_password(old_pass, new_pass, new_pass)

        service.lock_vault()
        success, _ = service.authenticate(new_pass)

        self.assertTrue(success)

    def test_change_master_password_preserves_secret_metadata(self):
        """Test that secret creation/update timestamps are preserved after password change."""
        service = self._create_service()

        service.setup_master_password("old_password", "old_password")
        # Re-authenticate since setup clears the key
        service.authenticate("old_password")

        service.add_secret("test_secret", "user", "pass", "url", "comment")

        # Get original secret timestamps
        secret_before = service.get_secret("test_secret")
        created_before = secret_before.get_create_date()

        # Change password
        service.change_master_password("old_password", "new_password", "new_password")

        # Verify timestamps are preserved immediately after change (before locking)
        secret_after = service.get_secret("test_secret")
        created_after = secret_after.get_create_date()

        self.assertEqual(created_before, created_after)

        # Lock and re-authenticate to verify persistence
        service.lock_vault()
        service.authenticate("new_password")
        secret_reloaded = service.get_secret("test_secret")
        created_reloaded = secret_reloaded.get_create_date()

        self.assertEqual(created_before, created_reloaded)


if __name__ == "__main__":
    unittest.main()
