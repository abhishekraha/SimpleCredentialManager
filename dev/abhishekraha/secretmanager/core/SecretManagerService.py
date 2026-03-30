import csv
import io
from datetime import datetime
from pathlib import Path

from dev.abhishekraha.secretmanager.codec import CodecUtils, SerDeUtils
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    APP_CONFIG_DIR,
    APP_HOME_DIR,
    BUG_REPORT_URL,
    DEFAULT_EXPORT_CSV,
    SECRET_FILE,
    SECRET_MANAGER_META_DATA,
)
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import (
    SecretManagerMetaDataManager,
)
from dev.abhishekraha.secretmanager.utils.AuditLogger import audit_action


class SecretManagerService:
    def __init__(self, client_name="unknown"):
        self._client_name = client_name
        self._metadata_manager = None
        self._secrets = {}

    def initialize(self):
        self._ensure_app_dirs()
        self._clear_session()
        if not SECRET_MANAGER_META_DATA.exists():
            self._metadata_manager = None
            self._audit("service_initialized", configured=False)
            return False
        try:
            self._metadata_manager = SerDeUtils.load(SECRET_MANAGER_META_DATA)
        except Exception as exc:
            self._audit(
                "service_initialization_failed",
                status="failed",
                reason=type(exc).__name__,
            )
            raise
        self._audit("service_initialized", configured=True)
        return True

    def is_initialized(self):
        return SECRET_MANAGER_META_DATA.exists()

    def is_unlocked(self):
        try:
            CodecUtils.get_derived_key()
            return True
        except (ValueError, TypeError):
            return False

    def setup_master_password(self, master_password, confirmation_password):
        self._ensure_app_dirs()
        if self.is_initialized():
            self._audit("initial_setup_rejected", status="failed", reason="already_initialized")
            raise ValueError("Credential manager is already initialized.")
        if not master_password:
            self._audit("initial_setup_rejected", status="failed", reason="empty_master_password")
            raise ValueError("Master password cannot be empty.")
        if master_password != confirmation_password:
            self._audit("initial_setup_rejected", status="failed", reason="password_mismatch")
            raise ValueError("Password mismatch. Please try again.")

        metadata = SecretManagerMetaDataManager()
        metadata.set_master_password(master_password)

        try:
            SerDeUtils.dump(metadata, SECRET_MANAGER_META_DATA)
            CodecUtils.derive_key(master_password, metadata.get_salt())
            SerDeUtils.dump_secrets({}, SECRET_FILE)
        except Exception:
            if SECRET_MANAGER_META_DATA.exists():
                SECRET_MANAGER_META_DATA.unlink()
            raise
        finally:
            CodecUtils.clear_derived_key()

        self._metadata_manager = metadata
        self._secrets = {}
        self._audit("initial_setup_completed")

    def authenticate(self, master_password):
        metadata = self._require_metadata()
        if metadata.clear_expired_lockout():
            self._persist_metadata()

        if metadata.is_locked_out():
            seconds = metadata.get_lockout_remaining_seconds()
            self._audit(
                "authentication_blocked_by_lockout",
                failed_attempts=metadata.get_failed_auth_attempts(),
                lockout_seconds=seconds,
            )
            return False, f"Too many failed attempts. Try again in {seconds} second(s)."

        if not master_password:
            self._audit("authentication_rejected", status="failed", reason="empty_master_password")
            return False, "Master password cannot be empty."

        if metadata.validate_master_password(master_password):
            had_failed_attempts = metadata.get_failed_auth_attempts() > 0
            if had_failed_attempts:
                metadata.reset_failed_auth_attempts()
            try:
                self._load_secrets()
            except ValueError as exc:
                CodecUtils.clear_derived_key()
                self._audit("vault_unlock_failed", status="failed", reason="vault_file_unreadable")
                return False, f"Vault file could not be opened: {exc}"
            if had_failed_attempts:
                self._persist_metadata()
            self._audit("authentication_succeeded", prior_failures=had_failed_attempts)
            return True, "Authentication succeeded."

        seconds = metadata.record_failed_auth_attempt()
        self._persist_metadata()
        if seconds:
            self._audit(
                "authentication_lockout_started",
                status="failed",
                failed_attempts=metadata.get_failed_auth_attempts(),
                lockout_seconds=seconds,
            )
            return False, f"Master password is invalid. Vault locked for {seconds} second(s)."

        remaining = metadata.get_remaining_attempts_before_lockout()
        self._audit(
            "authentication_failed",
            status="failed",
            failed_attempts=metadata.get_failed_auth_attempts(),
            attempts_before_lockout=remaining,
        )
        return False, (
            "Master password is invalid. "
            f"{remaining} attempt(s) remaining before temporary lockout."
        )

    def get_lockout_status(self):
        metadata = self._require_metadata()
        if metadata.clear_expired_lockout():
            self._persist_metadata()
        return {
            "is_locked_out": metadata.is_locked_out(),
            "remaining_seconds": metadata.get_lockout_remaining_seconds(),
            "failed_attempts": metadata.get_failed_auth_attempts(),
            "remaining_attempts_before_lockout": metadata.get_remaining_attempts_before_lockout(),
        }

    def lock_vault(self):
        had_active_session = self.is_unlocked() or bool(self._secrets)
        self._clear_session()
        if had_active_session:
            self._audit("vault_locked")

    def get_secret(self, secret_name):
        self._require_unlocked()
        return self._secrets.get(secret_name)

    def get_secret_records(self, filter_text=""):
        self._require_unlocked()
        query = (filter_text or "").strip().lower()
        secrets = list(self._secrets.values())
        if query:
            secrets = [
                secret
                for secret in secrets
                if query in " ".join(
                    [
                        secret.get_name().lower(),
                        secret.get_username().lower(),
                        secret.get_url().lower(),
                        secret.get_comments().lower(),
                    ]
                )
            ]
        return sorted(secrets, key=lambda secret: secret.get_name().lower())

    def get_secret_names(self, filter_text=""):
        return [secret.get_name() for secret in self.get_secret_records(filter_text)]

    def add_secret(self, name, username, password, url="", comments=""):
        self._require_unlocked()
        name = (name or "").strip()
        if not name:
            self._audit("secret_add_failed", status="failed", reason="empty_secret_name")
            raise ValueError("Secret name cannot be empty.")
        if name in self._secrets:
            self._audit("secret_add_failed", status="failed", reason="duplicate_secret_name", secret_name=name)
            raise ValueError("A secret with this name already exists.")
        self._secrets[name] = Secret(name, username or "", password or "", url or "", comments or "")
        self._persist_secrets()
        self._audit("secret_added", secret_name=name)

    def bulk_insert_secrets(self, csv_payload):
        self._require_unlocked()

        payload = (csv_payload or "").strip()
        if not payload:
            self._audit("bulk_insert_failed", status="failed", reason="empty_input")
            raise ValueError("Bulk insert input is empty.")

        expected_headers = ["name", "username", "password", "url", "comments"]
        rows = list(csv.reader(io.StringIO(payload)))
        if not rows or not rows[0]:
            self._audit("bulk_insert_failed", status="failed", reason="missing_header")
            raise ValueError("Bulk insert input must include a header row.")

        normalized_headers = [header.strip().lower() for header in rows[0]]
        if normalized_headers != expected_headers:
            self._audit(
                "bulk_insert_failed",
                status="failed",
                reason="invalid_headers",
                provided_headers=normalized_headers,
            )
            raise ValueError(
                "Bulk insert header must be exactly: name,username,password,url,comments"
            )

        prepared_secrets = []
        pending_names = set()
        skipped_blank_rows = 0
        validation_errors = []

        for line_number, row in enumerate(rows[1:], start=2):
            if not row or not any((value or "").strip() for value in row):
                skipped_blank_rows += 1
                continue

            if len(row) > len(expected_headers):
                validation_errors.append(
                    f"Line {line_number}: expected {len(expected_headers)} columns but found {len(row)}."
                )
                continue

            padded_row = row + [""] * (len(expected_headers) - len(row))
            normalized_row = {
                normalized_headers[index]: value
                for index, value in enumerate(padded_row)
            }
            if not any((value or "").strip() for value in normalized_row.values()):
                skipped_blank_rows += 1
                continue

            secret_name = (normalized_row.get("name") or "").strip()
            if not secret_name:
                validation_errors.append(f"Line {line_number}: secret name is required.")
                continue
            if secret_name in self._secrets or secret_name in pending_names:
                validation_errors.append(
                    f"Line {line_number}: a secret named '{secret_name}' already exists."
                )
                continue

            pending_names.add(secret_name)
            prepared_secrets.append(
                Secret(
                    secret_name,
                    normalized_row.get("username", "") or "",
                    normalized_row.get("password", "") or "",
                    normalized_row.get("url", "") or "",
                    normalized_row.get("comments", "") or "",
                )
            )

        if validation_errors:
            self._audit(
                "bulk_insert_failed",
                status="failed",
                reason="validation_error",
                error_count=len(validation_errors),
            )
            raise ValueError("\n".join(validation_errors[:5]))

        for secret in prepared_secrets:
            self._secrets[secret.get_name()] = secret

        if prepared_secrets:
            self._persist_secrets()
            for secret in prepared_secrets:
                self._audit("secret_added", secret_name=secret.get_name())

        summary = {
            "added": len(prepared_secrets),
            "skipped_blank_rows": skipped_blank_rows,
        }
        self._audit("bulk_insert_completed", **summary)
        return summary

    def update_secret(self, original_name, new_name, username, password, url="", comments=""):
        self._require_unlocked()
        original_name = (original_name or "").strip()
        if original_name not in self._secrets:
            self._audit("secret_update_failed", status="failed", reason="secret_not_found", secret_name=original_name)
            raise KeyError("Secret not found.")
        target_name = (new_name or "").strip() or original_name
        if target_name != original_name and target_name in self._secrets:
            self._audit(
                "secret_update_failed",
                status="failed",
                reason="duplicate_secret_name",
                secret_name=target_name,
            )
            raise ValueError("A secret with this name already exists.")

        secret = self._secrets.pop(original_name)
        secret.set_name(target_name)
        secret.set_username(username or "")
        secret.set_password(password or "")
        secret.set_url(url or "")
        secret.set_comments(comments or "")
        secret.set_update_date(datetime.now())
        self._secrets[target_name] = secret
        self._persist_secrets()
        self._audit(
            "secret_updated",
            secret_name=target_name,
            previous_secret_name=original_name,
            renamed=target_name != original_name,
        )

    def delete_secret(self, name):
        self._require_unlocked()
        name = (name or "").strip()
        if name not in self._secrets:
            self._audit("secret_delete_failed", status="failed", reason="secret_not_found", secret_name=name)
            raise KeyError("Secret not found.")
        del self._secrets[name]
        self._persist_secrets()
        self._audit("secret_deleted", secret_name=name)

    def export_secrets(self, target_path, overwrite=False):
        self._require_unlocked()
        target = Path(target_path)
        if target.exists() and not overwrite:
            self._audit("secrets_export_failed", status="failed", reason="target_exists", target_path=target)
            raise FileExistsError(f"Target file '{target}' already exists.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["name", "username", "password", "url", "comments", "created_at", "updated_at"])
            for secret in self.get_secret_records():
                writer.writerow(
                    [
                        secret.get_name(),
                        secret.get_username(),
                        secret.get_password(),
                        secret.get_url(),
                        secret.get_comments(),
                        secret.get_create_date().isoformat() if secret.get_create_date() else "",
                        secret.get_update_date().isoformat() if secret.get_update_date() else "",
                    ]
                )
        self._audit("secrets_exported", target_path=target, secret_count=len(self._secrets))
        return target

    def import_secrets(self, source_path, conflict_strategy="skip", rename_resolver=None):
        self._require_unlocked()
        source = Path(source_path)
        if not source.exists():
            self._audit("secrets_import_failed", status="failed", reason="source_missing", source_path=source)
            raise FileNotFoundError(f"Import file not found: {source}")
        if conflict_strategy not in {"skip", "overwrite", "rename"}:
            self._audit(
                "secrets_import_failed",
                status="failed",
                reason="unsupported_conflict_strategy",
                conflict_strategy=conflict_strategy,
            )
            raise ValueError("Unsupported conflict strategy.")
        if conflict_strategy == "rename" and rename_resolver is None:
            self._audit(
                "secrets_import_failed",
                status="failed",
                reason="missing_rename_resolver",
            )
            raise ValueError("A rename resolver is required for rename conflict strategy.")

        imported = 0
        overwritten = 0
        renamed = 0
        skipped = 0
        changes_made = False
        with open(source, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            expected = ["name", "username", "password", "url", "comments", "created_at", "updated_at"]
            if not reader.fieldnames or not all(column in reader.fieldnames for column in expected):
                self._audit("secrets_import_failed", status="failed", reason="invalid_csv_header", source_path=source)
                raise ValueError("CSV format invalid. Expected header: " + ",".join(expected))

            for row in reader:
                name = (row.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                if name in self._secrets:
                    if conflict_strategy == "skip":
                        skipped += 1
                        continue
                    if conflict_strategy == "rename":
                        original_name = name
                        name = (rename_resolver(name) or "").strip()
                        if not name:
                            skipped += 1
                            continue
                        if name == original_name:
                            overwritten += 1
                        elif name in self._secrets:
                            raise ValueError(
                                "Rename conflict resolution must return a unique, non-empty name."
                            )
                        else:
                            renamed += 1
                    else:
                        overwritten += 1
                else:
                    imported += 1
                self._secrets[name] = Secret(
                    name,
                    row.get("username", ""),
                    row.get("password", ""),
                    row.get("url", ""),
                    row.get("comments", ""),
                    create_date=_parse_datetime(row.get("created_at")) or datetime.now(),
                    update_date=_parse_datetime(row.get("updated_at")),
                )
                changes_made = True

        if changes_made:
            self._persist_secrets()
        summary = {
            "imported": imported,
            "overwritten": overwritten,
            "renamed": renamed,
            "skipped": skipped,
            "changes_made": changes_made,
        }
        self._audit(
            "secrets_imported",
            source_path=source,
            conflict_strategy=conflict_strategy,
            **summary,
        )
        return summary

    def record_secret_view(self, secret_name):
        self._require_unlocked()
        self._audit("secret_viewed", secret_name=secret_name)

    def record_secret_copy(self, secret_name, field_name="password"):
        self._require_unlocked()
        self._audit(
            "secret_copied_to_clipboard",
            secret_name=secret_name,
            field_name=field_name,
        )

    def record_secret_listing(self, result_count, filter_applied=False):
        self._require_unlocked()
        self._audit(
            "secrets_listed",
            result_count=result_count,
            filter_applied=bool(filter_applied),
        )

    def get_startup_recovery_instructions(self, error):
        message = str(error)
        if "unsupported legacy format" not in message and "Unsupported metadata version" not in message:
            return []

        instructions = [f"Back up the metadata file: {SECRET_MANAGER_META_DATA}"]
        if SECRET_FILE.exists():
            instructions.append(f"This release supports only v4 vault metadata. The current vault path is {SECRET_FILE}.")
            instructions.append(
                f"If this machine was expected to be migrated already, report it as a bug at {BUG_REPORT_URL}."
            )
            return instructions

        instructions.append(f"No vault file was found at {SECRET_FILE}.")
        if DEFAULT_EXPORT_CSV.exists():
            instructions.append(f"A CSV export is available at {DEFAULT_EXPORT_CSV}. Keep this file safe.")
            instructions.append(f"Rename or delete the unsupported metadata file: {SECRET_MANAGER_META_DATA}")
            instructions.append("Run the app again and create a new master password.")
            instructions.append("Use 'Import Secrets (CSV)' and select the CSV export file to restore your entries.")
            return instructions

        instructions.append(f"Rename or delete the unsupported metadata file: {SECRET_MANAGER_META_DATA}")
        instructions.append("Run the app again and create a new master password.")
        instructions.append("Re-enter your secrets manually, because no importable backup was found.")
        return instructions

    def _load_secrets(self):
        if not SECRET_FILE.exists():
            SerDeUtils.dump_secrets({}, SECRET_FILE)
        self._secrets = SerDeUtils.load_secrets(SECRET_FILE)

    def _persist_metadata(self):
        SerDeUtils.dump(self._require_metadata(), SECRET_MANAGER_META_DATA)

    def _persist_secrets(self):
        self._require_unlocked()
        SerDeUtils.dump_secrets(self._secrets, SECRET_FILE)

    def _ensure_app_dirs(self):
        APP_HOME_DIR.mkdir(parents=True, exist_ok=True)
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _clear_session(self):
        self._secrets = {}
        CodecUtils.clear_derived_key()

    def _require_metadata(self):
        if self._metadata_manager is None:
            raise RuntimeError("Credential manager metadata has not been initialized.")
        return self._metadata_manager

    def _require_unlocked(self):
        if not self.is_unlocked():
            raise RuntimeError("Master password has not been authenticated.")

    def _audit(self, action_name, status="success", **details):
        audit_action(
            action_name,
            client=self._client_name,
            status=status,
            **details,
        )


def _parse_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(value)
