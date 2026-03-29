import os
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone

from dev.abhishekraha.secretmanager.codec.CodecUtils import build_password_verifier, verify_password, \
    CURRENT_KEY_DERIVATION_VERSION
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import FAILED_AUTH_LOCKOUT_BASE_SECONDS, \
    FAILED_AUTH_LOCKOUT_MAX_SECONDS, FAILED_AUTH_LOCKOUT_THRESHOLD


class SecretManagerMetaDataManager:
    def __init__(
            self,
            salt=None,
            password_verifier=None,
            version=CURRENT_KEY_DERIVATION_VERSION,
            failed_auth_attempts=0,
            lockout_until=None,
    ):
        self._salt = salt or os.urandom(16)
        self._password_verifier = password_verifier
        self._version = version
        self._failed_auth_attempts = failed_auth_attempts
        self._lockout_until = lockout_until

    def get_salt(self):
        return self._salt

    def set_master_password(self, master_password):
        self._password_verifier = build_password_verifier(master_password, self._salt, version=self._version)

    def validate_master_password(self, master_password):
        if self._password_verifier is None:
            raise ValueError("Master password verifier has not been initialized.")
        return verify_password(master_password, self._salt, self._password_verifier, version=self._version)

    def set_version(self, version):
        self._version = version

    def get_version(self):
        return self._version

    def uses_deprecated_key_derivation(self):
        return self._version < CURRENT_KEY_DERIVATION_VERSION

    def get_failed_auth_attempts(self):
        return self._failed_auth_attempts

    def get_remaining_attempts_before_lockout(self):
        return max(0, FAILED_AUTH_LOCKOUT_THRESHOLD - self._failed_auth_attempts)

    def record_failed_auth_attempt(self, current_time=None):
        current_time = current_time or datetime.now(timezone.utc)
        self._failed_auth_attempts += 1
        lockout_seconds = self._get_lockout_seconds()
        self._lockout_until = (
            current_time + timedelta(seconds=lockout_seconds)
            if lockout_seconds
            else None
        )
        return lockout_seconds

    def reset_failed_auth_attempts(self):
        self._failed_auth_attempts = 0
        self._lockout_until = None

    def is_locked_out(self, current_time=None):
        if self._lockout_until is None:
            return False
        current_time = current_time or datetime.now(timezone.utc)
        return current_time < self._lockout_until

    def clear_expired_lockout(self, current_time=None):
        if self._lockout_until is None:
            return False
        current_time = current_time or datetime.now(timezone.utc)
        if current_time >= self._lockout_until:
            self._lockout_until = None
            return True
        return False

    def get_lockout_remaining_seconds(self, current_time=None):
        if self._lockout_until is None:
            return 0
        current_time = current_time or datetime.now(timezone.utc)
        if current_time >= self._lockout_until:
            return 0
        return int((self._lockout_until - current_time).total_seconds()) + 1

    def _get_lockout_seconds(self):
        if self._failed_auth_attempts < FAILED_AUTH_LOCKOUT_THRESHOLD:
            return 0
        exponent = self._failed_auth_attempts - FAILED_AUTH_LOCKOUT_THRESHOLD
        return min(
            FAILED_AUTH_LOCKOUT_BASE_SECONDS * (2 ** exponent),
            FAILED_AUTH_LOCKOUT_MAX_SECONDS,
        )

    def to_dict(self):
        return {
            "version": self._version,
            "salt": urlsafe_b64encode(self._salt).decode("ascii"),
            "password_verifier": self._password_verifier,
            "failed_auth_attempts": self._failed_auth_attempts,
            "lockout_until": self._lockout_until.isoformat() if self._lockout_until else None,
        }

    @classmethod
    def from_dict(cls, metadata_payload):
        salt = metadata_payload.get("salt")
        password_verifier = metadata_payload.get("password_verifier")
        if not salt or not password_verifier:
            raise ValueError("Metadata file is missing required fields.")
        return cls(
            salt=urlsafe_b64decode(salt.encode("ascii")),
            password_verifier=password_verifier,
            version=metadata_payload.get("version", 3),
            failed_auth_attempts=metadata_payload.get("failed_auth_attempts", 0),
            lockout_until=_parse_datetime(metadata_payload.get("lockout_until")),
        )


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    parsed_datetime = datetime.fromisoformat(value)
    if parsed_datetime.tzinfo is None:
        return parsed_datetime.replace(tzinfo=timezone.utc)
    return parsed_datetime.astimezone(timezone.utc)
