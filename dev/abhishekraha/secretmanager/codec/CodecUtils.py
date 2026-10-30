import base64
import hmac
import os
from typing import Optional, Tuple, Union

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from dev.abhishekraha.secretmanager.utils.SecureBuffer import SecureBuffer, zero_buffer

DERIVED_KEY = None
CURRENT_KEY_DERIVATION_VERSION = 4

# Check for argon2-cffi availability
try:
    import argon2.low_level
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False


def get_derived_key():
    global DERIVED_KEY
    if DERIVED_KEY is None:
        raise ValueError("Master password has not been authenticated.")
    if not isinstance(DERIVED_KEY, (bytes, bytearray)):
        raise TypeError(f"Derived key must be bytes or bytearray, received {type(DERIVED_KEY)}.")
    return bytes(DERIVED_KEY)


def set_derived_key(key):
    global DERIVED_KEY
    clear_derived_key()
    if isinstance(key, str):
        key = key.encode("ascii")
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError("Derived key must be bytes or bytearray.")
    DERIVED_KEY = bytearray(key)


def clear_derived_key():
    global DERIVED_KEY
    if DERIVED_KEY is not None:
        zero_buffer(DERIVED_KEY)
        DERIVED_KEY = None


# ---------------------------------------------------------------------------
# Argon2id / Scrypt Key Derivation and Envelope Encryption Utilities
# ---------------------------------------------------------------------------

def derive_master_km(master_password: str, salt: bytes, kdf_name: str = "auto") -> bytes:
    """
    Derives a 32-byte Master Key (KM) from master_password and salt.
    Uses Argon2id if available (or requested), otherwise Scrypt.
    """
    if not isinstance(salt, bytes):
        raise TypeError("Salt must be bytes.")

    pwd_bytes = master_password.encode("utf-8")
    with SecureBuffer(pwd_bytes) as sb_pwd:
        if (kdf_name == "argon2id" or kdf_name == "auto") and HAS_ARGON2:
            return argon2.low_level.hash_secret_raw(
                secret=sb_pwd.raw,
                salt=salt,
                time_cost=3,
                memory_cost=65536,  # 64 MB
                parallelism=4,
                hash_len=32,
                type=argon2.low_level.Type.ID,
            )
        else:
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=2 ** 14,
                r=8,
                p=1,
            )
            return kdf.derive(sb_pwd.raw)


def expand_km_keys(km: bytes) -> Tuple[bytes, bytes]:
    """
    Expands the 32-byte KM into:
    - kek (32 bytes) for AES-256-GCM wrapping of the DEK
    - auth_tag_key (32 bytes)
    """
    hkdf_kek = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=32,
        info=b"scm-envelope-kek-v1",
    )
    kek = hkdf_kek.derive(km)

    hkdf_auth = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=32,
        info=b"scm-envelope-auth-v1",
    )
    auth_key = hkdf_auth.derive(km)
    return kek, auth_key


def generate_and_wrap_dek(km: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Generates a new random 256-bit DEK (encoded as Fernet urlsafe key)
    and wraps it using AES-256-GCM under KEK derived from KM.
    Returns (raw_dek_fernet_bytes, wrapped_dek_b64, dek_nonce_b64).
    """
    raw_dek_bytes = Fernet.generate_key()
    kek, _ = expand_km_keys(km)

    aesgcm = AESGCM(kek)
    nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
    ciphertext = aesgcm.encrypt(nonce, raw_dek_bytes, b"scm-dek-v1")

    wrapped_dek_b64 = base64.urlsafe_b64encode(ciphertext).decode("ascii")
    dek_nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")

    return raw_dek_bytes, wrapped_dek_b64, dek_nonce_b64


def unwrap_dek(km: bytes, wrapped_dek_b64: str, dek_nonce_b64: str) -> Optional[bytes]:
    """
    Unwraps the DEK using AES-256-GCM under KEK derived from KM.
    Returns None if decryption / tag verification fails.
    """
    try:
        kek, _ = expand_km_keys(km)
        nonce = base64.urlsafe_b64decode(dek_nonce_b64.encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(wrapped_dek_b64.encode("ascii"))
        aesgcm = AESGCM(kek)
        raw_dek_bytes = aesgcm.decrypt(nonce, ciphertext, b"scm-dek-v1")
        return raw_dek_bytes
    except Exception:
        return None


def derive_blind_index_key(dek: Union[bytes, str]) -> bytes:
    """
    Derives a dedicated blind index key from the DEK using HKDF-Expand.
    This ensures domain separation so blind indexes cannot be inverted or correlated across vaults.
    """
    if isinstance(dek, str):
        dek = dek.encode("ascii")
    hkdf = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=32,
        info=b"scm-blind-index-key-v1",
    )
    return hkdf.derive(dek)


def _derive_key_material(master_password, salt, length):
    kdf = Scrypt(
        salt=salt,
        length=length,
        n=2 ** 14,
        r=8,
        p=1,
    )
    return kdf.derive(master_password.encode("utf-8"))


def _build_session_material(master_password, salt):
    derived_material = _derive_key_material(master_password, salt, 64)
    password_verifier_material = derived_material[:32]
    vault_key_material = derived_material[32:]
    password_verifier = base64.urlsafe_b64encode(password_verifier_material).decode("ascii")
    vault_key = base64.urlsafe_b64encode(vault_key_material)
    return password_verifier, vault_key


def derive_key(master_password, salt):
    _, vault_key = _build_session_material(master_password, salt)
    set_derived_key(vault_key)
    return vault_key


def build_vault_key(master_password, salt):
    _, vault_key = _build_session_material(master_password, salt)
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


def encrypt_with_key(plaintext, key, is_file=False):
    if not isinstance(plaintext, bytes):
        plaintext = plaintext.encode("utf-8")
    encoder = Fernet(key)
    return encoder.encrypt(plaintext)


def decrypt(token, is_file=False):
    decoder = Fernet(get_derived_key())
    try:
        plaintext = decoder.decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt data with the current master password.") from exc
    return plaintext if is_file else plaintext.decode("utf-8")


def decrypt_with_key(token, key, is_file=False):
    decoder = Fernet(key)
    try:
        plaintext = decoder.decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt data with the supplied password.") from exc
    return plaintext if is_file else plaintext.decode("utf-8")
