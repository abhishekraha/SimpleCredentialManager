import json
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from dev.abhishekraha.secretmanager.utils.AuditLogger import audit_action


class AuditLoggerTests(unittest.TestCase):
    def test_audit_action_writes_client_status_and_sanitized_details(self):
        audit_log_file = Path("audit.log")
        mocked_open = mock_open()

        with patch.object(Path, "exists", return_value=False):
            with patch("builtins.open", mocked_open):
                audit_action(
                    "secret_copied_to_clipboard",
                    client="ui",
                    status="success",
                    log_file=audit_log_file,
                    secret_name="github",
                    target_path=Path("export.csv"),
                    password="super-secret",
                )

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
