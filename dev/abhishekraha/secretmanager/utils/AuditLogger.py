import json
import os
from datetime import datetime, timezone

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import AUDIT_LOG_FILE


def log_event(event_type, log_file=AUDIT_LOG_FILE, **details):
    event_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **details,
    }

    log_file.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not log_file.exists()
    with open(log_file, "a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(event_record, sort_keys=True) + "\n")

    if is_new_file and os.name != "nt":
        os.chmod(log_file, 0o600)
