import os

from dev.abhishekraha.secretmanager.codec.CodecUtils import derive_key, encrypt_password, decrypt_password


class SecretManagerMetaData:
    def __init__(self):
        self._salt = os.urandom(16)
        self._encrypted_master_password = None

    def get_salt(self):
        return self._salt

    def set_master_password(self, master_password: str):
        derive_key(master_password, self._salt)
        self._encrypted_master_password = encrypt_password(master_password)

    def validate_master_password(self, master_password: str) -> bool:
        return decrypt_password(self._encrypted_master_password).__eq__(master_password)
