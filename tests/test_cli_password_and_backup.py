import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import SimpleCredentialManagerCli as cli


class CliPasswordAndBackupTests(unittest.TestCase):
    @patch.object(cli, "SERVICE", new_callable=MagicMock)
    @patch.object(cli, "_session_secure_input")
    @patch.object(
        cli,
        "_session_input",
        side_effect=["github", "alice", "g", "https://example.com", "primary credential"],
    )
    def test_add_secret_can_generate_password(
        self,
        mocked_session_input,
        mocked_session_secure_input,
        mocked_service,
    ):
        mocked_service.generate_password.return_value = "Auto#Generated123"

        with patch("sys.stdout", new_callable=io.StringIO) as mocked_stdout:
            cli._add_secret()

        mocked_session_secure_input.assert_not_called()
        mocked_service.add_secret.assert_called_once_with(
            "github",
            "alice",
            "Auto#Generated123",
            "https://example.com",
            "primary credential",
        )
        self.assertIn("Generated password:", mocked_stdout.getvalue())

    @patch.object(cli, "SERVICE", new_callable=MagicMock)
    def test_import_secrets_detects_and_uses_encrypted_backup_flow(self, mocked_service):
        with TemporaryDirectory() as temp_dir:
            backup_file = Path(temp_dir) / "secrets_backup.scmbackup"
            backup_file.write_text("{}", encoding="utf-8")
            mocked_service.detect_import_format.return_value = "encrypted_backup"
            mocked_service.import_encrypted_backup.return_value = {
                "imported": 1,
                "overwritten": 0,
                "renamed": 0,
                "skipped": 0,
                "changes_made": True,
            }

            with patch.object(cli, "_session_input", side_effect=[str(backup_file)]):
                with patch.object(cli, "_session_secure_input", return_value="backup-passphrase"):
                    with patch("sys.stdout", new_callable=io.StringIO) as mocked_stdout:
                        cli._import_secrets()

        mocked_service.import_encrypted_backup.assert_called_once()
        mocked_service.import_secrets.assert_not_called()
        self.assertIn("Import complete and data persisted.", mocked_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
