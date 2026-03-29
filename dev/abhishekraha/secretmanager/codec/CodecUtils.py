import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DERIVED_KEY = None
CURRENT_KEY_DERIVATION_VERSION = 4
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


def _derive_key_material(master_password, salt, length):
    kdf = Scrypt(
        salt=salt,
        length=length,
        n=2 ** 14,
        r=8,
        p=1,
    )
    return kdf.derive(master_password.encode("utf-8"))


def _build_session_material(master_password, salt, version=CURRENT_KEY_DERIVATION_VERSION):
    if version < CURRENT_KEY_DERIVATION_VERSION:
        return _build_session_material_v3(master_password, salt)
    return _build_session_material_v4(master_password, salt)


def _build_session_material_v4(master_password, salt):
    derived_material = _derive_key_material(master_password, salt, 64)
    password_verifier_material = derived_material[:32]
    vault_key_material = derived_material[32:]
    password_verifier = base64.urlsafe_b64encode(password_verifier_material).decode("ascii")
    vault_key = base64.urlsafe_b64encode(vault_key_material)
    return password_verifier, vault_key


def _build_session_material_v3(master_password, salt):
    master_key = _derive_key_material(master_password, salt, 32)
    password_verifier = base64.urlsafe_b64encode(
        _legacy_expand_key_material(master_key, PASSWORD_VERIFIER_CONTEXT)
    ).decode("ascii")
    vault_key = base64.urlsafe_b64encode(
        _legacy_expand_key_material(master_key, VAULT_KEY_CONTEXT)
    )
    return password_verifier, vault_key


def _legacy_expand_key_material(master_key, context):
    # codeql[py/weak-sensitive-data-hashing] Deprecated compatibility path for legacy v2/v3 vaults only.
    return hmac.new(master_key, context, hashlib.sha256).digest()


def derive_key(master_password, salt, version=CURRENT_KEY_DERIVATION_VERSION):
    _, vault_key = _build_session_material(master_password, salt, version=version)
    set_derived_key(vault_key)
    return vault_key


def build_password_verifier(master_password, salt, version=CURRENT_KEY_DERIVATION_VERSION):
    password_verifier, _ = _build_session_material(master_password, salt, version=version)
    return password_verifier


def verify_password(master_password, salt, password_verifier, version=CURRENT_KEY_DERIVATION_VERSION):
    derived_password_verifier, vault_key = _build_session_material(master_password, salt, version=version)
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
