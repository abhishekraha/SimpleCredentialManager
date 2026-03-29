import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DERIVED_KEY = None
PASSWORD_VERIFIER_CONTEXT = b"simple-credential-manager-password-verifier"
VAULT_KEY_CONTEXT = b"simple-credential-manager-vault-key"


def get_derived_key():
    global DERIVED_KEY
    if DERIVED_KEY is None:
        raise ValueError("Master password has not been authenticated.")
    if not isinstance(DERIVED_KEY, bytes):
        raise TypeError(f"Derived key must be bytes, received {type(DERIVED_KEY)}.")
    return DERIVED_KEY


def set_derived_key(key):
    global DERIVED_KEY
    if not isinstance(key, bytes):
        raise TypeError("Derived key must be bytes.")
    DERIVED_KEY = key


def clear_derived_key():
    global DERIVED_KEY
    DERIVED_KEY = None


def _derive_master_key(master_password, salt):
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2 ** 14,
        r=8,
        p=1,
    )
    return kdf.derive(master_password.encode("utf-8"))


def _build_session_material(master_password, salt):
    master_key = _derive_master_key(master_password, salt)
    password_verifier = base64.urlsafe_b64encode(
        hmac.new(master_key, PASSWORD_VERIFIER_CONTEXT, hashlib.sha256).digest()
    ).decode("ascii")
    vault_key = base64.urlsafe_b64encode(
        hmac.new(master_key, VAULT_KEY_CONTEXT, hashlib.sha256).digest()
    )
    return password_verifier, vault_key


def derive_key(master_password, salt):
    _, vault_key = _build_session_material(master_password, salt)
    set_derived_key(vault_key)
    return vault_key


def build_password_verifier(master_password, salt):
    password_verifier, _ = _build_session_material(master_password, salt)
    return password_verifier


def verify_password(master_password, salt, password_verifier):
    derived_password_verifier, vault_key = _build_session_material(master_password, salt)
    if hmac.compare_digest(derived_password_verifier, password_verifier):
        set_derived_key(vault_key)
        return True
    clear_derived_key()
    return False


def encrypt(plaintext, is_file=False):
    if not isinstance(plaintext, bytes):
        plaintext = plaintext.encode("utf-8")
    encoder = Fernet(get_derived_key())
    return encoder.encrypt(plaintext)


def decrypt(token, is_file=False):
    decoder = Fernet(get_derived_key())
    try:
        plaintext = decoder.decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt data with the current master password.") from exc
    return plaintext if is_file else plaintext.decode("utf-8")
