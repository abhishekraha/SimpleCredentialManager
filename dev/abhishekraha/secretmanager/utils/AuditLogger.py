import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import AUDIT_LOG_FILE

SENSITIVE_DETAIL_FRAGMENTS = (
    "password",
    "token",
    "verifier",
    "clipboard_text",
    "master",
    "vault_key",
    "secret_value",
)


def log_event(event_type, log_file=AUDIT_LOG_FILE, **details):
    log_file = Path(log_file)
    event_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **_sanitize_details(details),
    }

    log_file.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not log_file.exists()
    with open(log_file, "a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(event_record, sort_keys=True) + "\n")

    if is_new_file and os.name != "nt":
        try:
            os.chmod(log_file, 0o600)
        except FileNotFoundError:
            # Tests may mock writes without creating a real file on disk.
            pass


def audit_action(action_name, client="unknown", status="success", log_file=AUDIT_LOG_FILE, **details):
    log_event(
        action_name,
        log_file=log_file,
        client=client,
        status=status,
        **details,
    )


def _sanitize_details(details):
    return {
        key: _sanitize_value(key, value)
        for key, value in details.items()
    }


def _sanitize_value(key, value):
    normalized_key = (key or "").lower()
    if any(fragment in normalized_key for fragment in SENSITIVE_DETAIL_FRAGMENTS):
        return "<redacted>"

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            nested_key: _sanitize_value(nested_key, nested_value)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [
            _sanitize_value(key, nested_value)
            for nested_value in value
        ]
    return value
