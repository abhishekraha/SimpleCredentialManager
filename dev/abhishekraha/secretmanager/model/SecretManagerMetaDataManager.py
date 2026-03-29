import os
from base64 import urlsafe_b64decode, urlsafe_b64encode

from dev.abhishekraha.secretmanager.codec.CodecUtils import build_password_verifier, verify_password


class SecretManagerMetaDataManager:
    def __init__(self, salt=None, password_verifier=None, version=2):
        self._salt = salt or os.urandom(16)
        self._password_verifier = password_verifier
        self._version = version

    def get_salt(self):
        return self._salt

    def set_master_password(self, master_password):
        self._password_verifier = build_password_verifier(master_password, self._salt)

    def validate_master_password(self, master_password):
        if self._password_verifier is None:
            raise ValueError("Master password verifier has not been initialized.")
        return verify_password(master_password, self._salt, self._password_verifier)

    def to_dict(self):
        return {
            "version": self._version,
            "salt": urlsafe_b64encode(self._salt).decode("ascii"),
            "password_verifier": self._password_verifier,
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
            version=metadata_payload.get("version", 2),
        )
