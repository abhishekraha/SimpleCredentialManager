import hashlib
import json
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Optional, Union

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import APP_CONFIG_DIR


class DeviceRegistry:
    """Manages out-of-band device whitelist and enrollment tokens for SCM Server Mode."""

    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        if storage_path is not None:
            self._storage_path = Path(storage_path)
        else:
            self._storage_path = APP_CONFIG_DIR / "devices.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        if not self._storage_path.exists():
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                "enrollment_token": "",
                "devices": {}
            }
            self._write_data(initial_data)

    def _read_data(self) -> dict:
        if not self._storage_path.exists():
            return {"enrollment_token": "", "devices": {}}
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"enrollment_token": "", "devices": {}}

    def _write_data(self, data: dict) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._storage_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self._storage_path)

    @staticmethod
    def _compute_fingerprint(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def get_or_create_enrollment_token(self) -> str:
        """Retrieves existing enrollment token or generates a new one if not present."""
        data = self._read_data()
        token = data.get("enrollment_token")
        if not token:
            token = secrets.token_urlsafe(32)
            data["enrollment_token"] = token
            self._write_data(data)
        return token

    def rotate_enrollment_token(self) -> str:
        """Generates, saves, and returns a new enrollment token."""
        data = self._read_data()
        new_token = secrets.token_urlsafe(32)
        data["enrollment_token"] = new_token
        self._write_data(data)
        return new_token

    def request_enrollment(self, device_name: str, client_ip: str = "") -> dict:
        """Requests enrollment for a new device, setting status to PENDING.
        Returns enrollment details including device_id, fingerprint, and device_token.
        """
        device_id = f"dev-{uuid.uuid4().hex[:8]}"
        device_token = secrets.token_hex(32)
        fingerprint = self._compute_fingerprint(device_token)
        now_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        device_record = {
            "device_id": device_id,
            "device_name": device_name,
            "client_ip": client_ip,
            "fingerprint": fingerprint,
            "status": "PENDING",
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        data = self._read_data()
        if "devices" not in data:
            data["devices"] = {}

        data["devices"][device_id] = device_record
        self._write_data(data)

        # Return full details to caller
        res = dict(device_record)
        res["device_token"] = device_token
        return res

    def list_devices(self) -> list[dict]:
        """Returns list of all registered devices."""
        data = self._read_data()
        devices = data.get("devices", {})
        return list(devices.values())

    def approve_device(self, fingerprint_or_id: str) -> bool:
        """Approves a device identified by device_id or fingerprint."""
        data = self._read_data()
        devices = data.get("devices", {})

        target_id = None
        for dev_id, record in devices.items():
            if dev_id == fingerprint_or_id or record.get("fingerprint") == fingerprint_or_id:
                target_id = dev_id
                break

        if not target_id:
            return False

        devices[target_id]["status"] = "APPROVED"
        devices[target_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        self._write_data(data)
        return True

    def revoke_device(self, fingerprint_or_id: str) -> bool:
        """Revokes a device identified by device_id or fingerprint."""
        data = self._read_data()
        devices = data.get("devices", {})

        target_id = None
        for dev_id, record in devices.items():
            if dev_id == fingerprint_or_id or record.get("fingerprint") == fingerprint_or_id:
                target_id = dev_id
                break

        if not target_id:
            return False

        devices[target_id]["status"] = "REVOKED"
        devices[target_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        self._write_data(data)
        return True

    def is_device_approved(self, device_token: str) -> bool:
        """Checks if the device corresponding to device_token has status APPROVED."""
        if not device_token:
            return False
        fingerprint = self._compute_fingerprint(device_token)
        data = self._read_data()
        devices = data.get("devices", {})

        for record in devices.values():
            if record.get("fingerprint") == fingerprint:
                return record.get("status") == "APPROVED"
        return False
