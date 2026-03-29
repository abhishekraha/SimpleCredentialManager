import json
import os
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from dev.abhishekraha.secretmanager.utils.AuditLogger import audit_action


class AuditLoggerTests(unittest.TestCase):
    def test_audit_action_writes_client_status_and_sanitized_details(self):
        audit_log_file = Path("audit.log")
        mocked_open = mock_open()
        original_exists = Path.exists

        def fake_exists(path_obj):
            if path_obj == audit_log_file:
                return False
            return original_exists(path_obj)

        with patch.object(Path, "exists", autospec=True, side_effect=fake_exists):
            with patch("builtins.open", mocked_open):
                with patch("os.chmod") as mocked_chmod:
                    audit_action(
                        "secret_copied_to_clipboard",
                        client="ui",
                        status="success",
                        log_file=audit_log_file,
                        secret_name="github",
                        target_path=Path("export.csv"),
                        password="super-secret",
                    )

        if os.name != "nt":
            mocked_chmod.assert_called_once_with(audit_log_file, 0o600)

        write_call = mocked_open().write.call_args
        self.assertIsNotNone(write_call)
        audit_record = json.loads(write_call.args[0].strip())
        self.assertEqual("secret_copied_to_clipboard", audit_record["event"])
        self.assertEqual("ui", audit_record["client"])
        self.assertEqual("success", audit_record["status"])
        self.assertEqual("github", audit_record["secret_name"])
        self.assertEqual("export.csv", audit_record["target_path"])
        self.assertEqual("<redacted>", audit_record["password"])
        self.assertIn("timestamp", audit_record)


if __name__ == "__main__":
    unittest.main()
