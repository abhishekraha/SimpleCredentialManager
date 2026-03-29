from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DERIVED_KEY = None


def get_derived_key():
    global DERIVED_KEY
    if DERIVED_KEY is None:
        print("DERIVED_KEY NOT FOUND")
        exit(1)
    elif not isinstance(DERIVED_KEY, bytes):
        print(f"DERIVED_KEY is of type {type(DERIVED_KEY)}. Expected bytes")
        exit(1)

    return DERIVED_KEY


def set_derived_key(key):
    global DERIVED_KEY
    DERIVED_KEY = key


def derive_key(master_password, salt):
    kdf = Scrypt(
        salt=salt,
        length=32,  # 32 bytes = 256-bit key
        n=2 ** 14,  # CPU/memory cost
        r=8,
        p=1,
    )
    key = kdf.derive(master_password.encode())
    set_derived_key(urlsafe_b64encode(key))  # Fernet-friendly format


def encrypt(plaintext, is_file = False):
    if not is_file:
        plaintext = plaintext.encode()
    encoder = Fernet(get_derived_key())
    token = encoder.encrypt(plaintext)
    return token


def decrypt(token, is_file = False):
    decoder = Fernet(get_derived_key())
    plaintext = decoder.decrypt(token)
    return plaintext.decode() if not is_file else plaintext