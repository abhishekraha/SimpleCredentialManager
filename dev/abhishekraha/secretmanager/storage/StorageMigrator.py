import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from dev.abhishekraha.secretmanager.codec import CodecUtils, SerDeUtils
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    APP_CONFIG_DIR,
    APP_HOME_DIR,
    SECRET_FILE,
    SECRET_MANAGER_META_DATA,
    VAULT_DB_FILE,
)
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import (
    SecretManagerMetaDataManager,
)
from dev.abhishekraha.secretmanager.storage.SqliteVaultStorage import SqliteVaultStorage

logger = logging.getLogger(__name__)


class StorageMigrator:
    """
    Handles atomic migration from legacy flat-file vault (.simpleCredentialManager.secret
    and .simpleCredentialManager.metadata) to embedded SQLite vault (vault.scmdb).
    """

    def __init__(
        self,
        legacy_secret_file: Optional[Union[str, Path]] = None,
        legacy_meta_file: Optional[Union[str, Path]] = None,
        target_db_file: Optional[Union[str, Path]] = None,
    ):
        self._legacy_secret_file = Path(legacy_secret_file) if legacy_secret_file else SECRET_FILE
        self._legacy_meta_file = Path(legacy_meta_file) if legacy_meta_file else SECRET_MANAGER_META_DATA
        self._target_db_file = Path(target_db_file) if target_db_file else VAULT_DB_FILE

    @property
    def legacy_secret_file(self) -> Path:
        return self._legacy_secret_file

    @property
    def legacy_meta_file(self) -> Path:
        return self._legacy_meta_file

    @property
    def target_db_file(self) -> Path:
        return self._target_db_file

    def is_migration_needed(self) -> bool:
        """
        Detects if legacy vault files exist and new .scmdb does not.
        """
        legacy_exists = self._legacy_meta_file.exists() or self._legacy_secret_file.exists()
        sqlite_exists = self._target_db_file.exists()
        return legacy_exists and not sqlite_exists

    def migrate(self, master_password: str) -> Dict[str, Any]:
        """
        Migrates existing secrets dictionary and metadata into the new SQLite database in an atomic transaction.
        Renames old files to .backup to guarantee zero data loss.
        Returns a summary dictionary of the migration.
        """
        if not self.is_migration_needed():
            return {
                "migrated": False,
                "reason": "Migration not needed or SQLite database already exists.",
                "count": 0,
            }

        if not self._legacy_meta_file.exists():
            raise FileNotFoundError(f"Legacy metadata file not found: {self._legacy_meta_file}")

        # Load metadata
        metadata = SerDeUtils.load(self._legacy_meta_file)
        if not metadata.validate_master_password(master_password):
            raise ValueError("Master password is invalid. Cannot decrypt legacy vault for migration.")

        # Active DERIVED_KEY is now set in session by validate_master_password
        dek = CodecUtils.get_derived_key()
        salt = metadata.get_salt()
        blind_key = CodecUtils.derive_blind_index_key(dek)

        # Load secrets
        secrets: Dict[str, Secret] = {}
        if self._legacy_secret_file.exists():
            secrets = SerDeUtils.load_secrets(self._legacy_secret_file)

        # Initialize SQLite database
        storage = SqliteVaultStorage(self._target_db_file)
        storage.init_db()

        # Build wrapped_dek if present, or wrap current dek
        wrapped_dek_bytes = b""
        if hasattr(metadata, "get_wrapped_dek") and metadata.get_wrapped_dek():
            wrapped_dek_bytes = metadata.get_wrapped_dek().encode("utf-8")
        else:
            # Generate wrapped DEK representation
            wrapped_dek_bytes = dek

        kdf_params = {
            "version": metadata.get_version(),
            "kdf": getattr(metadata, "get_kdf", lambda: "scrypt")(),
        }

        lockout_data = {
            "failed_auth_attempts": metadata.get_failed_auth_attempts(),
            "lockout_until": (
                metadata._lockout_until.isoformat() if metadata._lockout_until else None
            ),
        }

        # Atomic transaction: populate SQLite database
        try:
            storage.init_vault(
                salt=salt,
                wrapped_dek=wrapped_dek_bytes,
                kdf_params=kdf_params,
                kdf_algorithm=kdf_params["kdf"],
                version=metadata.get_version(),
                lockout_data=lockout_data,
            )

            for secret in secrets.values():
                storage.save_secret(secret, dek, blind_key)

        except Exception as exc:
            # Clean up target DB if creation failed
            if self._target_db_file.exists():
                self._target_db_file.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to migrate vault into SQLite: {exc}") from exc

        # Safe rename of old files to .backup
        meta_backup = self._legacy_meta_file.with_suffix(".metadata.backup")
        secret_backup = self._legacy_secret_file.with_suffix(".secret.backup")

        try:
            if self._legacy_meta_file.exists():
                os.replace(self._legacy_meta_file, meta_backup)
            if self._legacy_secret_file.exists():
                os.replace(self._legacy_secret_file, secret_backup)
        except OSError as exc:
            logger.warning("Could not rename legacy files to backup: %s", exc)

        return {
            "migrated": True,
            "count": len(secrets),
            "meta_backup": str(meta_backup),
            "secret_backup": str(secret_backup),
            "target_db": str(self._target_db_file),
        }
