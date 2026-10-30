import base64
import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from cryptography.fernet import Fernet, InvalidToken

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import VAULT_DB_FILE
from dev.abhishekraha.secretmanager.model.Secret import Secret


def compute_blind_index(value: str, blind_key: bytes) -> str:
    """
    Computes a deterministic, salted HMAC-SHA256 blind index for normalized searchable terms.
    Case-insensitive lookup: normalized to lowercase.
    """
    normalized = (value or "").strip().lower().encode("utf-8")
    h = hmac.new(blind_key, normalized, hashlib.sha256)
    return h.hexdigest()


class SqliteVaultStorage:
    """
    SQLite-backed embedded storage engine providing row-level authenticated encryption
    for Simple Credential Manager secrets.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self._db_path = Path(db_path) if db_path is not None else VAULT_DB_FILE

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Creates tables and indexes if they do not exist, and runs migrations."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vault_meta (
                    version INTEGER PRIMARY KEY,
                    salt BLOB NOT NULL,
                    kdf_algorithm TEXT NOT NULL,
                    kdf_params TEXT NOT NULL,
                    wrapped_dek BLOB NOT NULL,
                    lockout_data TEXT,
                    created_at TEXT NOT NULL,
                    preferred_ui TEXT DEFAULT 'modern'
                );
                """
            )
            # Ensure preferred_ui column exists if table was created in an older schema
            cursor = conn.execute("PRAGMA table_info(vault_meta);")
            cols = [r["name"] for r in cursor.fetchall()]
            if "preferred_ui" not in cols:
                conn.execute("ALTER TABLE vault_meta ADD COLUMN preferred_ui TEXT DEFAULT 'modern';")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS secrets (
                    id TEXT PRIMARY KEY,
                    blind_index TEXT NOT NULL,
                    name_encrypted BLOB NOT NULL,
                    username_encrypted BLOB NOT NULL,
                    payload_encrypted BLOB NOT NULL,
                    category TEXT DEFAULT 'login',
                    is_favorite INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_secrets_blind ON secrets(blind_index);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_secrets_fav ON secrets(is_favorite);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_secrets_cat ON secrets(category);"
            )

    def init_vault(
        self,
        salt: bytes,
        wrapped_dek: bytes,
        kdf_params: Optional[Dict[str, Any]] = None,
        kdf_algorithm: str = "scrypt",
        version: int = 5,
        lockout_data: Optional[Dict[str, Any]] = None,
        preferred_ui: str = "modern",
    ) -> None:
        """
        Initializes vault metadata record in vault_meta.
        """
        self.init_db()
        params_str = json.dumps(kdf_params or {})
        lockout_str = json.dumps(lockout_data) if lockout_data is not None else None
        now_str = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO vault_meta (
                    version, salt, kdf_algorithm, kdf_params, wrapped_dek, lockout_data, created_at, preferred_ui
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    version,
                    salt,
                    kdf_algorithm,
                    params_str,
                    wrapped_dek,
                    lockout_str,
                    now_str,
                    preferred_ui,
                ),
            )

    def get_vault_meta(self) -> Optional[Dict[str, Any]]:
        """Retrieves vault metadata dictionary or None if uninitialized."""
        if not self._db_path.exists():
            return None
        self.init_db()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT version, salt, kdf_algorithm, kdf_params, wrapped_dek, lockout_data, created_at, preferred_ui FROM vault_meta LIMIT 1;"
            )
            row = cursor.fetchone()
            if not row:
                return None

            kdf_params_parsed = json.loads(row["kdf_params"]) if row["kdf_params"] else {}
            lockout_parsed = json.loads(row["lockout_data"]) if row["lockout_data"] else None
            pref_ui = row["preferred_ui"] if "preferred_ui" in row.keys() and row["preferred_ui"] else "modern"

            return {
                "version": row["version"],
                "salt": row["salt"],
                "kdf_algorithm": row["kdf_algorithm"],
                "kdf_params": kdf_params_parsed,
                "wrapped_dek": row["wrapped_dek"],
                "lockout_data": lockout_parsed,
                "created_at": row["created_at"],
                "preferred_ui": pref_ui,
            }

    def update_vault_meta(
        self,
        wrapped_dek: Optional[bytes] = None,
        lockout_data: Optional[Dict[str, Any]] = None,
        salt: Optional[bytes] = None,
        kdf_algorithm: Optional[str] = None,
        kdf_params: Optional[Dict[str, Any]] = None,
        preferred_ui: Optional[str] = None,
    ) -> None:
        """Updates metadata fields in vault_meta."""
        meta = self.get_vault_meta()
        if not meta:
            raise RuntimeError("Vault metadata does not exist.")

        new_wrapped_dek = wrapped_dek if wrapped_dek is not None else meta["wrapped_dek"]
        new_salt = salt if salt is not None else meta["salt"]
        new_kdf_algo = kdf_algorithm if kdf_algorithm is not None else meta["kdf_algorithm"]
        new_pref_ui = preferred_ui if preferred_ui is not None else meta.get("preferred_ui", "modern")
        new_kdf_params = (
            json.dumps(kdf_params)
            if kdf_params is not None
            else json.dumps(meta["kdf_params"])
        )
        new_lockout = (
            json.dumps(lockout_data)
            if lockout_data is not None
            else (json.dumps(meta["lockout_data"]) if meta["lockout_data"] is not None else None)
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE vault_meta SET
                    salt = ?,
                    kdf_algorithm = ?,
                    kdf_params = ?,
                    wrapped_dek = ?,
                    lockout_data = ?,
                    preferred_ui = ?
                WHERE version = ?;
                """,
                (
                    new_salt,
                    new_kdf_algo,
                    new_kdf_params,
                    new_wrapped_dek,
                    new_lockout,
                    new_pref_ui,
                    meta["version"],
                ),
            )

    def get_ui_preference(self) -> str:
        """
        Retrieves the preferred UI mode ('modern' or 'classic').
        Defaults to 'modern'.
        """
        if not self._db_path.exists():
            return "modern"
        self.init_db()
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT preferred_ui FROM vault_meta LIMIT 1;")
            row = cursor.fetchone()
            if row and row["preferred_ui"]:
                return row["preferred_ui"]
        return "modern"

    def set_ui_preference(self, preferred_ui: str) -> None:
        """
        Stores the preferred UI mode ('modern' or 'classic') in vault_meta.
        """
        if preferred_ui not in ("modern", "classic"):
            raise ValueError(f"Invalid UI preference: {preferred_ui}. Expected 'modern' or 'classic'.")
        self.init_db()
        meta = self.get_vault_meta()
        if meta:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE vault_meta SET preferred_ui = ? WHERE version = ?;",
                    (preferred_ui, meta["version"]),
                )
        else:
            # If vault_meta row does not exist yet, store or update preference in metadata / fallback
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO vault_meta (
                        version, salt, kdf_algorithm, kdf_params, wrapped_dek, lockout_data, created_at, preferred_ui
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        0,
                        b"",
                        "",
                        "{}",
                        b"",
                        None,
                        datetime.now(timezone.utc).isoformat(),
                        preferred_ui,
                    ),
                )

    def _get_fernet(self, dek: Union[bytes, str]) -> Fernet:
        if isinstance(dek, str):
            dek = dek.encode("ascii")
        return Fernet(dek)

    def save_secret(self, secret: Secret, dek: Union[bytes, str], blind_key: bytes) -> None:
        """
        Saves or updates a secret using row-level authenticated encryption.
        Uses blind_index for matching if existing record exists under the same secret name.
        """
        self.init_db()
        fernet = self._get_fernet(dek)
        name = secret.get_name()
        b_idx = compute_blind_index(name, blind_key)

        name_encrypted = fernet.encrypt(name.encode("utf-8"))
        username_encrypted = fernet.encrypt(secret.get_username().encode("utf-8"))

        payload_dict = {
            "password": secret.get_password(),
            "url": secret.get_url(),
            "comments": secret.get_comments(),
            "totp_secret": secret.get_totp_secret(),
            "tags": secret.get_tags(),
        }
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        payload_encrypted = fernet.encrypt(payload_bytes)

        category = secret.get_category()
        is_fav = 1 if secret.is_favorite() else 0
        create_str = (
            secret.get_create_date().isoformat()
            if secret.get_create_date()
            else datetime.now(timezone.utc).isoformat()
        )
        update_str = (
            secret.get_update_date().isoformat()
            if secret.get_update_date()
            else None
        )

        with self._get_connection() as conn:
            # Check if record with this blind index already exists
            cursor = conn.execute(
                "SELECT id, created_at FROM secrets WHERE blind_index = ?;",
                (b_idx,),
            )
            row = cursor.fetchone()
            if row:
                rec_id = row["id"]
                orig_created_at = row["created_at"] or create_str
                conn.execute(
                    """
                    UPDATE secrets SET
                        name_encrypted = ?,
                        username_encrypted = ?,
                        payload_encrypted = ?,
                        category = ?,
                        is_favorite = ?,
                        created_at = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        name_encrypted,
                        username_encrypted,
                        payload_encrypted,
                        category,
                        is_fav,
                        orig_created_at,
                        update_str or datetime.now(timezone.utc).isoformat(),
                        rec_id,
                    ),
                )
            else:
                rec_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO secrets (
                        id, blind_index, name_encrypted, username_encrypted, payload_encrypted,
                        category, is_favorite, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        rec_id,
                        b_idx,
                        name_encrypted,
                        username_encrypted,
                        payload_encrypted,
                        category,
                        is_fav,
                        create_str,
                        update_str,
                    ),
                )

    def get_secret(
        self, name: str, dek: Union[bytes, str], blind_key: bytes
    ) -> Optional[Secret]:
        """
        Retrieves and fully decrypts a secret by name using its blind index.
        Returns Secret or None if not found.
        """
        if not self._db_path.exists():
            return None
        self.init_db()
        b_idx = compute_blind_index(name, blind_key)
        fernet = self._get_fernet(dek)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, blind_index, name_encrypted, username_encrypted, payload_encrypted,
                       category, is_favorite, created_at, updated_at
                FROM secrets WHERE blind_index = ? LIMIT 1;
                """,
                (b_idx,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            try:
                decrypted_name = fernet.decrypt(row["name_encrypted"]).decode("utf-8")
                decrypted_username = fernet.decrypt(row["username_encrypted"]).decode("utf-8")
                payload_raw = fernet.decrypt(row["payload_encrypted"]).decode("utf-8")
                payload = json.loads(payload_raw)
            except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError("Failed to decrypt secret payload.") from exc

            return Secret(
                name=decrypted_name,
                username=decrypted_username,
                password=payload.get("password", ""),
                url=payload.get("url", ""),
                comments=payload.get("comments", ""),
                create_date=_parse_db_datetime(row["created_at"]),
                update_date=_parse_db_datetime(row["updated_at"]),
                category=row["category"] or "login",
                is_favorite=bool(row["is_favorite"]),
                totp_secret=payload.get("totp_secret"),
                tags=payload.get("tags") or [],
            )

    def list_secrets(
        self, dek: Union[bytes, str], category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lazy loading: decrypts only record names and usernames without decrypting passwords into RAM.
        Returns a list of dicts: id, name, username, category, is_favorite, created_at, updated_at.
        """
        if not self._db_path.exists():
            return []
        self.init_db()
        fernet = self._get_fernet(dek)

        query = (
            "SELECT id, blind_index, name_encrypted, username_encrypted, category, is_favorite, created_at, updated_at FROM secrets"
        )
        params: List[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY is_favorite DESC, created_at ASC;"

        records = []
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                try:
                    decrypted_name = fernet.decrypt(row["name_encrypted"]).decode("utf-8")
                    decrypted_username = fernet.decrypt(row["username_encrypted"]).decode("utf-8")
                except InvalidToken as exc:
                    raise ValueError("Failed to decrypt record headers.") from exc

                records.append(
                    {
                        "id": row["id"],
                        "name": decrypted_name,
                        "username": decrypted_username,
                        "category": row["category"] or "login",
                        "is_favorite": bool(row["is_favorite"]),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
        return sorted(records, key=lambda r: r["name"].lower())

    def delete_secret(self, name: str, blind_key: bytes) -> bool:
        """Deletes a secret by its blind index. Returns True if deleted, False if not found."""
        if not self._db_path.exists():
            return False
        self.init_db()
        b_idx = compute_blind_index(name, blind_key)
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM secrets WHERE blind_index = ?;",
                (b_idx,),
            )
            return cursor.rowcount > 0

    def get_all_secrets(self, dek: Union[bytes, str]) -> Dict[str, Secret]:
        """
        Decrypts and returns all secrets as a mapping of name -> Secret (used for full exports and backups).
        """
        if not self._db_path.exists():
            return {}
        self.init_db()
        fernet = self._get_fernet(dek)
        results: Dict[str, Secret] = {}

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, name_encrypted, username_encrypted, payload_encrypted,
                       category, is_favorite, created_at, updated_at
                FROM secrets;
                """
            )
            for row in cursor.fetchall():
                try:
                    name = fernet.decrypt(row["name_encrypted"]).decode("utf-8")
                    username = fernet.decrypt(row["username_encrypted"]).decode("utf-8")
                    payload_raw = fernet.decrypt(row["payload_encrypted"]).decode("utf-8")
                    payload = json.loads(payload_raw)
                except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError("Failed to decrypt secret payload during export.") from exc

                results[name] = Secret(
                    name=name,
                    username=username,
                    password=payload.get("password", ""),
                    url=payload.get("url", ""),
                    comments=payload.get("comments", ""),
                    create_date=_parse_db_datetime(row["created_at"]),
                    update_date=_parse_db_datetime(row["updated_at"]),
                    category=row["category"] or "login",
                    is_favorite=bool(row["is_favorite"]),
                    totp_secret=payload.get("totp_secret"),
                    tags=payload.get("tags") or [],
                )
        return results

    def count_secrets(self) -> int:
        """Returns the total number of secret rows in the database."""
        if not self._db_path.exists():
            return 0
        self.init_db()
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM secrets;")
            return cursor.fetchone()[0]


def _parse_db_datetime(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None
