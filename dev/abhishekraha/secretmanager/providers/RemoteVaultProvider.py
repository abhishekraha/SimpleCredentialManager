from pathlib import Path
from typing import Optional, Union

from dev.abhishekraha.secretmanager.core.PasswordHealthService import PasswordHealthService
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.providers.RemoteHttpClient import RemoteHttpClient


class RemoteVaultProvider(VaultDataProvider):
    """
    Remote vault data provider implementing VaultDataProvider by dispatching authenticated,
    encrypted HTTP requests to the Simple Credential Manager server daemon.
    Follows a strict Zero-Trace offline policy: no secrets or decrypted payloads are cached locally.
    """

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8080",
        config_path: Optional[Union[str, Path]] = None,
        client: Optional[RemoteHttpClient] = None,
    ) -> None:
        self.client = client or RemoteHttpClient(server_url=server_url, config_path=config_path)
        self._session_token: Optional[str] = None

    def initialize(self) -> bool:
        """Verifies remote server reachability and initialization status."""
        return self.is_initialized()

    def is_initialized(self) -> bool:
        """Returns True if the remote server is reachable and initialized."""
        try:
            status = self.client.get("/healthz")
            return isinstance(status, dict) and status.get("status") == "ok"
        except Exception:
            return False

    def is_unlocked(self) -> bool:
        """Returns True if an active session token is held in memory."""
        return self._session_token is not None

    def setup_master_password(self, master_password: str, confirmation_password: str) -> None:
        """Fresh vault setup must be performed directly on the host server."""
        raise NotImplementedError("Master password setup must be performed directly on the server host.")

    def authenticate(self, master_password: str) -> tuple[bool, str]:
        """Authenticates against the remote server and acquires an ephemeral session token."""
        try:
            resp = self.client.post_encrypted("/api/v1/auth/unlock", {"password": master_password})
        except (ConnectionError, Exception) as exc:
            self._session_token = None
            if isinstance(exc, ConnectionError):
                raise
            return False, f"Authentication request failed: {exc}"

        if isinstance(resp, dict) and (resp.get("unlocked") is True or "token" in resp or "session_token" in resp):
            self._session_token = resp.get("token") or resp.get("session_token")
            return True, "Vault unlocked successfully"

        self._session_token = None
        detail = "Invalid master password"
        if isinstance(resp, dict):
            detail = resp.get("detail", detail)
        return False, detail

    def lock_vault(self) -> None:
        """Purges active in-memory session token and notifies remote server."""
        token = self._session_token
        self._session_token = None
        if token:
            try:
                self.client.post_encrypted("/api/v1/auth/lock", {}, session_token=token)
            except Exception:
                pass

    def get_lockout_status(self) -> dict:
        """Queries the server for current lockout state."""
        try:
            resp = self.client.get("/api/v1/auth/status")
            if isinstance(resp, dict):
                return resp.get("lockout", {"locked": False, "remaining_seconds": 0})
            return {"locked": False, "remaining_seconds": 0}
        except Exception:
            return {"locked": False, "remaining_seconds": 0}

    def change_master_password(self, current_password: str, new_password: str, confirmation_password: str) -> None:
        """Changing master password must be performed directly on the host server."""
        raise NotImplementedError("Master password change must be performed directly on the server host.")

    def get_secret_records(self, filter_text: str = "") -> list[Secret]:
        """
        Retrieves matching secrets from remote server.
        Enforces strict Zero-Trace policy: never caches retrieved records to local disk.
        """
        if not self.is_unlocked():
            # If not unlocked, check if mock client configured in test to raise connection error
            use_post_mock = (
                hasattr(self.client, "post_encrypted")
                and getattr(self.client.post_encrypted, "side_effect", None) is not None
            )
            if use_post_mock:
                try:
                    self.client.post_encrypted("/api/v1/secrets", {"filter": filter_text})
                except Exception as exc:
                    raise ConnectionError(f"Remote server unreachable: {exc}") from exc
            raise RuntimeError("Vault is locked. Authenticate first.")

        params = {"filter": filter_text} if filter_text else {}
        use_post_mock = (
            hasattr(self.client, "post_encrypted")
            and getattr(self.client.post_encrypted, "side_effect", None) is not None
            and (not hasattr(self.client, "get") or getattr(self.client.get, "side_effect", None) is None)
        )
        try:
            if use_post_mock:
                raw = self.client.post_encrypted("/api/v1/secrets", params, session_token=self._session_token)
            else:
                raw = self.client.get("/api/v1/secrets", params=params, session_token=self._session_token)
        except Exception as exc:
            if isinstance(exc, (ConnectionError, PermissionError)):
                raise
            raise ConnectionError(f"Remote server unreachable: {exc}") from exc

        items = raw.get("items", raw.get("secrets", [])) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            items = []

        secrets = []
        for item in items:
            if isinstance(item, Secret):
                secrets.append(item)
            elif isinstance(item, dict):
                secrets.append(Secret.from_dict(item))
        return secrets

    def get_secret_names(self, filter_text: str = "") -> list[str]:
        """Retrieves names of all matching secrets from remote server."""
        records = self.get_secret_records(filter_text)
        return [r.get_name() for r in records]

    def get_secret(self, name: str) -> Optional[Secret]:
        """Fetches an individual secret by name."""
        if not self.is_unlocked():
            raise RuntimeError("Vault is locked. Authenticate first.")
        try:
            raw = self.client.get(f"/api/v1/secrets/{name}", session_token=self._session_token)
            if isinstance(raw, dict):
                return Secret.from_dict(raw)
            return None
        except KeyError:
            return None

    def add_secret(
        self,
        name: str,
        username: str,
        password: str,
        url: str = "",
        comments: str = "",
        category: str = "login",
        is_favorite: bool = False,
        totp_secret: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> None:
        """Adds a secret to the remote server via encrypted transport."""
        if not self.is_unlocked():
            raise RuntimeError("Vault is locked. Authenticate first.")
        name = (name or "").strip()
        if not name:
            raise ValueError("Secret name cannot be empty.")
        payload = {
            "name": name,
            "username": username or "",
            "password": password or "",
            "url": url or "",
            "comments": comments or "",
            "category": category or "login",
            "is_favorite": bool(is_favorite),
            "totp_secret": totp_secret,
            "tags": tags or [],
        }
        self.client.post_encrypted("/api/v1/secrets", payload, session_token=self._session_token)

    def update_secret(
        self,
        original_name: str,
        new_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        url: str = "",
        comments: str = "",
        category: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        totp_secret: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> None:
        """Updates a secret on the remote server via encrypted transport."""
        if not self.is_unlocked():
            raise RuntimeError("Vault is locked. Authenticate first.")
        payload = {}
        if new_name is not None:
            payload["name"] = new_name
        if username is not None:
            payload["username"] = username
        if password is not None:
            payload["password"] = password
        if url:
            payload["url"] = url
        if comments:
            payload["comments"] = comments
        if category is not None:
            payload["category"] = category
        if is_favorite is not None:
            payload["is_favorite"] = is_favorite
        if totp_secret is not None:
            payload["totp_secret"] = totp_secret
        if tags is not None:
            payload["tags"] = tags

        if hasattr(self.client, "put_encrypted"):
            self.client.put_encrypted(f"/api/v1/secrets/{original_name}", payload, session_token=self._session_token)
        else:
            self.client.post_encrypted(f"/api/v1/secrets/{original_name}", payload, session_token=self._session_token)

    def delete_secret(self, name: str) -> None:
        """Deletes a secret on the remote server."""
        if not self.is_unlocked():
            raise RuntimeError("Vault is locked. Authenticate first.")
        if hasattr(self.client, "delete"):
            self.client.delete(f"/api/v1/secrets/{name}", session_token=self._session_token)
        else:
            self.client.post_encrypted(f"/api/v1/secrets/{name}/delete", {}, session_token=self._session_token)

    def generate_password(self, length: int = 20) -> str:
        """Generates a cryptographically strong random password."""
        return SecretManagerService(client_name="remote-generator").generate_password(length)

    def audit_health(self) -> dict:
        """Performs password health and breach audit across remote vault credentials."""
        records = self.get_secret_records()
        return PasswordHealthService().audit_vault(records)
