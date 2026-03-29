import json
import os
import tempfile
from pathlib import Path

from dev.abhishekraha.secretmanager.codec import CodecUtils
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager


def dump(data, file_name, override=False):
    if override and Path(file_name).exists():
        raise FileExistsError(f"File {file_name} already exists")
    payload = json.dumps(data.to_dict(), indent=2).encode("utf-8")
    _write_bytes_atomic(Path(file_name), payload)


def load(file_name):
    if not Path(file_name).exists():
        raise FileNotFoundError(f"File {file_name} does not exist")
    try:
        with open(file_name, "r", encoding="utf-8") as file_handle:
            return SecretManagerMetaDataManager.from_dict(json.load(file_handle))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Metadata file is unreadable or uses an unsupported legacy format."
        ) from exc


def dump_secrets(data, file_name, override=False):
    if override and Path(file_name).exists():
        raise FileExistsError(f"File {file_name} already exists")
    serialized_secrets = {
        name: secret.to_dict() if hasattr(secret, "to_dict") else secret
        for name, secret in data.items()
    }
    data_bytes = json.dumps(serialized_secrets, indent=2).encode("utf-8")
    encrypted_bytes = CodecUtils.encrypt(data_bytes, is_file=True)
    _write_bytes_atomic(Path(file_name), encrypted_bytes)


def load_secrets(file_name):
    secret_file = Path(file_name)
    if not secret_file.exists():
        raise FileNotFoundError(f"File {file_name} does not exist")

    encrypted_bytes = secret_file.read_bytes()
    if not encrypted_bytes:
        return {}

    try:
        data_bytes = CodecUtils.decrypt(encrypted_bytes, is_file=True)
        decoded_payload = json.loads(data_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Vault file is unreadable or corrupt.") from exc
    return {
        name: Secret.from_dict(secret_payload)
        for name, secret_payload in decoded_payload.items()
    }


def _write_bytes_atomic(target_file, payload):
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target_file.parent,
            delete=False,
            prefix=f"{target_file.name}.",
            suffix=".tmp",
    ) as temp_file:
        temp_file.write(payload)
        temp_file_path = Path(temp_file.name)

    try:
        os.replace(temp_file_path, target_file)
    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()

    if os.name != "nt":
        os.chmod(target_file, 0o600)
