import os

from dev.abhishekraha.secretmanager.codec import SerDeUtils
from dev.abhishekraha.secretmanager.codec.CodecUtils import derive_key, encrypt_password, decrypt_password
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import SECRET_MANAGER_META_DATA


class SecretManagerMetaDataManager:
    def __init__(self):
        self._salt = os.urandom(16)
        self._incorrect_password_attempts = 0
        self._incorrect_password_threshold = 2  # Warn user after 2 incorrect attempts
        self._max_incorrect_password_attempts = 3
        self._encrypted_master_password = None

    def get_salt(self):
        return self._salt

    def set_master_password(self, master_password):
        derive_key(master_password, self._salt)
        self._encrypted_master_password = encrypt_password(master_password)

    def validate_master_password(self, master_password):
        return decrypt_password(self._encrypted_master_password).__eq__(master_password)

    def increment_incorrect_password_attempts(self):
        self._incorrect_password_attempts += 1
        SerDeUtils.dump(self, SECRET_MANAGER_META_DATA)

    def reset_incorrect_password_attempts(self):
        self._incorrect_password_attempts = 0
        SerDeUtils.dump(self, SECRET_MANAGER_META_DATA)

    def get_incorrect_password_attempts(self):
        return self._incorrect_password_attempts

    def get_incorrect_password_threshold(self):
        return self._incorrect_password_threshold

    def get_max_incorrect_password_attempts(self):
        return self._max_incorrect_password_attempts
