import base64
import json
import os
from typing import Any, Dict, Union

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


TRANSPORT_SALT = b"scm-transport-v1"
TRANSPORT_INFO = b"scm-payload-encryption-v1"
KEY_LENGTH = 32  # 256 bits for AES-256-GCM
NONCE_LENGTH = 12  # standard 12-byte (96-bit) nonce for AES-GCM


def derive_transport_key(device_token: str) -> bytes:
    """
    Derives a 32-byte Transport Encryption Key (TEK) from device_token using HKDF.
    HKDF(algorithm=hashes.SHA256(), length=32, salt=b"scm-transport-v1", info=b"scm-payload-encryption-v1")
    """
    if not isinstance(device_token, str):
        raise TypeError(f"device_token must be a string, got {type(device_token).__name__}")
    if not device_token.strip():
        raise ValueError("device_token must not be empty")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=TRANSPORT_SALT,
        info=TRANSPORT_INFO,
    )
    return hkdf.derive(device_token.encode("utf-8"))


def encrypt_payload(data: Union[dict, list, str], device_token: str) -> dict:
    """
    Encrypts arbitrary data (dict, list, or str) using AES-256-GCM and the derived transport key.
    Returns:
        dict: {"iv": "<base64 12-byte nonce>", "ciphertext": "<base64 ciphertext+tag>"}
    """
    key = derive_transport_key(device_token)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LENGTH)

    if isinstance(data, (dict, list)):
        payload_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")
    elif isinstance(data, str):
        # We wrap strings in JSON or raw UTF-8:
        # To maintain seamless round-trip typing, we encode as JSON string
        payload_bytes = json.dumps(data).encode("utf-8")
    else:
        payload_bytes = json.dumps(data).encode("utf-8")

    ciphertext = aesgcm.encrypt(nonce, payload_bytes, None)

    return {
        "iv": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_payload(payload_dict: dict, device_token: str) -> Union[dict, list, str, Any]:
    """
    Decrypts a payload dict {"iv": ..., "ciphertext": ...} using AES-256-GCM and the derived transport key.
    Returns parsed JSON object or string.
    """
    if not isinstance(payload_dict, dict):
        raise ValueError("payload_dict must be a dictionary containing 'iv' and 'ciphertext'")

    if "iv" not in payload_dict or "ciphertext" not in payload_dict:
        raise ValueError("payload_dict missing 'iv' or 'ciphertext' keys")

    iv_str = payload_dict["iv"]
    ct_str = payload_dict["ciphertext"]

    if not isinstance(iv_str, str) or not isinstance(ct_str, str):
        raise ValueError("'iv' and 'ciphertext' must be base64-encoded strings")

    try:
        nonce = base64.b64decode(iv_str.encode("ascii"), validate=True)
        ciphertext = base64.b64decode(ct_str.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError(f"Failed to base64 decode iv or ciphertext: {exc}") from exc

    key = derive_transport_key(device_token)
    aesgcm = AESGCM(key)

    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)

    try:
        return json.loads(decrypted_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return decrypted_bytes.decode("utf-8")
