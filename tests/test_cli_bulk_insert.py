import io
import unittest
from unittest.mock import MagicMock, patch

import SimpleCredentialManagerCli as cli


class CliBulkInsertTests(unittest.TestCase):
    @patch.object(cli, "SERVICE", new_callable=MagicMock)
    @patch.object(cli, "_session_input", side_effect=["github,alice,s3cr3t,https://github.com,primary", ""])
    def test_bulk_insert_prepends_default_header_when_rows_only_are_entered(
        self,
        mocked_session_input,
        mocked_service,
    ):
        mocked_service.bulk_insert_secrets.return_value = {
            "added": 1,
            "skipped_blank_rows": 0,
        }

        with patch("sys.stdout", new_callable=io.StringIO) as mocked_stdout:
            cli._bulk_insert_secrets()

        mocked_service.bulk_insert_secrets.assert_called_once_with(
            "name,username,password,url,comments\n"
            "github,alice,s3cr3t,https://github.com,primary"
        )
        self.assertIn("1 secret(s) added", mocked_stdout.getvalue())

    @patch.object(cli, "SERVICE", new_callable=MagicMock)
    @patch.object(
        cli,
        "_session_input",
        side_effect=[
            "name,username,password,url,comments",
            "email,bob,p4ss,https://example.com,backup",
            "",
        ],
    )
    def test_bulk_insert_accepts_a_pasted_header_without_duplication(
        self,
        mocked_session_input,
        mocked_service,
    ):
        mocked_service.bulk_insert_secrets.return_value = {
            "added": 1,
            "skipped_blank_rows": 0,
        }

        with patch("sys.stdout", new_callable=io.StringIO):
            cli._bulk_insert_secrets()

        mocked_service.bulk_insert_secrets.assert_called_once_with(
            "name,username,password,url,comments\n"
            "email,bob,p4ss,https://example.com,backup"
        )

    @patch.object(cli, "SERVICE", new_callable=MagicMock)
    @patch.object(cli, "_session_input", side_effect=[""])
    def test_bulk_insert_cancels_when_no_rows_are_entered(self, mocked_session_input, mocked_service):
        with patch("sys.stdout", new_callable=io.StringIO) as mocked_stdout:
            cli._bulk_insert_secrets()

        mocked_service.bulk_insert_secrets.assert_not_called()
        self.assertIn("Bulk insert cancelled", mocked_stdout.getvalue())

    @patch.object(cli, "clear_screen")
    @patch.object(cli, "SERVICE", new_callable=MagicMock)
    @patch.object(cli, "_session_input", side_effect=cli.IdleTimeoutError("timed out"))
    def test_run_authenticated_session_locks_vault_after_idle_timeout(
        self,
        mocked_session_input,
        mocked_service,
        mocked_clear_screen,
    ):
        with patch("time.sleep"):
            with patch("sys.stdout", new_callable=io.StringIO) as mocked_stdout:
                result = cli._run_authenticated_session()

        self.assertEqual("locked", result)
        mocked_service.lock_vault.assert_called_once()
        mocked_clear_screen.assert_called_once()
        self.assertIn("Vault locked after", mocked_stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
