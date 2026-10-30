import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from dev.abhishekraha.secretmanager.cli.ModernCli import app
from dev.abhishekraha.secretmanager.codec import CodecUtils
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.core.TotpService import TotpService


class ModernCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.mock_meta = self.temp_path / ".metadata"
        self.mock_secret = self.temp_path / ".secret"
        self.mock_db = self.temp_path / "vault.scmdb"

        self.patches = [
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.SECRET_MANAGER_META_DATA", self.mock_meta),
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.SECRET_FILE", self.mock_secret),
            patch("dev.abhishekraha.secretmanager.config.SecretManagerConfig.VAULT_DB_FILE", self.mock_db),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_MANAGER_META_DATA", self.mock_meta),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.SECRET_FILE", self.mock_secret),
            patch("dev.abhishekraha.secretmanager.core.SecretManagerService.VAULT_DB_FILE", self.mock_db),
        ]
        for p in self.patches:
            p.start()

        # Initialize the test vault
        self.master_pwd = "MasterPassword123!"
        self.service = SecretManagerService(client_name="test")
        self.service.setup_master_password(self.master_pwd, self.master_pwd)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        CodecUtils.clear_derived_key()
        self.temp_dir.cleanup()

    def test_cli_help(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Simple Credential Manager", result.output)
        self.assertIn("list", result.output)
        self.assertIn("get", result.output)
        self.assertIn("add", result.output)
        self.assertIn("totp", result.output)
        self.assertIn("health", result.output)

    def test_cli_add_and_get_secret(self):
        # Add a new credential
        # Inputs: master password
        add_result = self.runner.invoke(
            app,
            [
                "add",
                "GitHubWork",
                "--username",
                "alice_dev",
                "--password",
                "SecureToken999!",
                "--category",
                "developer",
                "--tags",
                "work,git,vcs",
            ],
            input=f"{self.master_pwd}\n",
        )
        self.assertEqual(add_result.exit_code, 0, f"Output: {add_result.output}")
        self.assertIn("Successfully added credential 'GitHubWork'", add_result.output)

        # Get the credential with --show
        get_result = self.runner.invoke(
            app,
            ["get", "GitHubWork", "--show"],
            input=f"{self.master_pwd}\n",
        )
        self.assertEqual(get_result.exit_code, 0)
        self.assertIn("GitHubWork", get_result.output)
        self.assertIn("alice_dev", get_result.output)
        self.assertIn("SecureToken999!", get_result.output)
        self.assertIn("developer", get_result.output)

    def test_cli_get_secret_json(self):
        # Add a secret first
        self.runner.invoke(
            app,
            ["add", "AWS_Prod", "--username", "admin", "--password", "SecretAWS123!"],
            input=f"{self.master_pwd}\n",
        )

        # Retrieve JSON output
        get_json = self.runner.invoke(
            app,
            ["get", "AWS_Prod", "--json"],
            input=f"{self.master_pwd}\n",
        )
        self.assertEqual(get_json.exit_code, 0)
        # Find json block in output (ignoring Master Password prompt)
        json_start = get_json.output.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(get_json.output[json_start:].strip())
        self.assertEqual(data["name"], "AWS_Prod")
        self.assertEqual(data["username"], "admin")
        self.assertEqual(data["password"], "SecretAWS123!")

    def test_cli_get_secret_clip(self):
        # Add secret
        self.runner.invoke(
            app,
            ["add", "BankLogin", "--username", "bob", "--password", "BankPwd888!"],
            input=f"{self.master_pwd}\n",
        )

        with patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.SecureClipboardManager.copy", return_value=True) as mock_copy:
            get_clip = self.runner.invoke(
                app,
                ["get", "BankLogin", "--clip"],
                input=f"{self.master_pwd}\n",
            )
            self.assertEqual(get_clip.exit_code, 0)
            mock_copy.assert_called_once_with("BankPwd888!", clear_timeout_seconds=30)
            self.assertIn("copied to clipboard", get_clip.output)

    def test_cli_add_with_generate(self):
        result = self.runner.invoke(
            app,
            ["add", "GeneratedItem", "--username", "testuser", "--generate"],
            input=f"{self.master_pwd}\n",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Generated password:", result.output)
        self.assertIn("Successfully added credential 'GeneratedItem'", result.output)

    def test_cli_list_credentials(self):
        # Add credentials
        self.runner.invoke(
            app,
            ["add", "Alpha", "--username", "user1", "--password", "pass1", "--category", "infra"],
            input=f"{self.master_pwd}\n",
        )
        self.runner.invoke(
            app,
            ["add", "Beta", "--username", "user2", "--password", "pass2", "--category", "login"],
            input=f"{self.master_pwd}\n",
        )

        # List all
        list_all = self.runner.invoke(app, ["list"], input=f"{self.master_pwd}\n")
        self.assertEqual(list_all.exit_code, 0)
        self.assertIn("Alpha", list_all.output)
        self.assertIn("Beta", list_all.output)

        # List with filter
        list_filter = self.runner.invoke(
            app, ["list", "--filter", "Alpha"], input=f"{self.master_pwd}\n"
        )
        self.assertEqual(list_filter.exit_code, 0)
        self.assertIn("Alpha", list_filter.output)
        self.assertNotIn("Beta", list_filter.output)

    def test_cli_totp_command(self):
        # Base32 secret for testing: JBSWY3DPEHPK3PXP
        test_secret = "JBSWY3DPEHPK3PXP"
        self.runner.invoke(
            app,
            [
                "add",
                "GoogleAccount",
                "--username",
                "user@gmail.com",
                "--password",
                "P@ssw0rd123!",
                "--totp",
                test_secret,
            ],
            input=f"{self.master_pwd}\n",
        )

        # Run totp command
        totp_result = self.runner.invoke(
            app,
            ["totp", "GoogleAccount"],
            input=f"{self.master_pwd}\n",
        )
        self.assertEqual(totp_result.exit_code, 0)
        self.assertIn("2FA Code: GoogleAccount", totp_result.output)
        self.assertIn("Valid for:", totp_result.output)

        # Test with --clip
        with patch("dev.abhishekraha.secretmanager.utils.SecureClipboardManager.SecureClipboardManager.copy", return_value=True) as mock_clip:
            totp_clip = self.runner.invoke(
                app,
                ["totp", "GoogleAccount", "--clip"],
                input=f"{self.master_pwd}\n",
            )
            self.assertEqual(totp_clip.exit_code, 0)
            mock_clip.assert_called_once()
            self.assertIn("copied to clipboard", totp_clip.output)

    def test_cli_health_audit(self):
        # Add one weak password and duplicates
        self.runner.invoke(
            app,
            ["add", "WeakItem1", "--username", "u1", "--password", "123456"],
            input=f"{self.master_pwd}\n",
        )
        self.runner.invoke(
            app,
            ["add", "WeakItem2", "--username", "u2", "--password", "123456"],
            input=f"{self.master_pwd}\n",
        )

        health_result = self.runner.invoke(
            app,
            ["health"],
            input=f"{self.master_pwd}\n",
        )
        self.assertEqual(health_result.exit_code, 0)
        self.assertIn("Vault Security Health Score", health_result.output)
        self.assertIn("Weak Passwords", health_result.output)
        self.assertIn("Reused Passwords", health_result.output)

    def test_cli_authentication_failure(self):
        result = self.runner.invoke(
            app,
            ["list"],
            input="WrongPassword\nWrongPassword\nWrongPassword\n",
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Master password is invalid", result.output)

    def test_cli_interactive_fallback(self):
        with patch("SimpleCredentialManagerCli.run_legacy_cli") as mock_cli:
            result = self.runner.invoke(app, ["interactive"])
            mock_cli.assert_called_once()


if __name__ == "__main__":
    unittest.main()
