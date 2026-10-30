import secrets
import time
from typing import Any, Dict, Optional

from dev.abhishekraha.secretmanager.codec import CodecUtils
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import SESSION_IDLE_LOCK_SECONDS


class ServerSessionManager:
    """
    Manages active authenticated client sessions and tracks inactivity for SCM Server Mode.
    
    When active sessions expire or all sessions are terminated, it triggers
    vault locking on SecretManagerService and clears master derived key material in memory.
    """

    def __init__(
        self,
        service: Optional[Any] = None,
        idle_timeout_seconds: int = SESSION_IDLE_LOCK_SECONDS,
    ):
        self._service = service
        self._idle_timeout_seconds = int(idle_timeout_seconds)
        # Session storage mapping: session_token -> dict(device_id, created_at, last_active)
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, device_id: str) -> str:
        """
        Generates a cryptographically random session token, registers the session,
        and returns the token.
        """
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[token] = {
            "device_id": str(device_id),
            "created_at": now,
            "last_active": now,
        }
        return token

    def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Retrieves raw session record if present, else None."""
        return self._sessions.get(session_token)

    def validate_session(self, session_token: str) -> bool:
        """
        Checks if token exists and hasn't exceeded idle_timeout_seconds.
        If active, updates last_active to current time and returns True.
        If expired or not found, calls terminate_session and returns False.
        """
        if not session_token or session_token not in self._sessions:
            return False

        session = self._sessions[session_token]
        elapsed = time.time() - session.get("last_active", 0)

        if elapsed > self._idle_timeout_seconds:
            self.terminate_session(session_token)
            return False

        session["last_active"] = time.time()
        return True

    def terminate_session(self, session_token: str) -> None:
        """
        Removes session. If zero active sessions remain, triggers vault locking
        and key zeroization.
        """
        if session_token in self._sessions:
            del self._sessions[session_token]

        if len(self._sessions) == 0:
            self._lock_vault_if_unlocked()

    def check_and_sweep_expired(self) -> int:
        """
        Sweeps all expired sessions. If no active sessions remain and vault is unlocked,
        triggers vault locking and memory clearing.
        Returns the count of swept sessions.
        """
        now = time.time()
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if (now - session.get("last_active", 0)) > self._idle_timeout_seconds
        ]

        for token in expired_tokens:
            if token in self._sessions:
                del self._sessions[token]

        if expired_tokens and len(self._sessions) == 0:
            self._lock_vault_if_unlocked()

        return len(expired_tokens)

    def is_vault_unlocked(self) -> bool:
        """Proxies service.is_unlocked(). Returns False if service is None."""
        if self._service is None:
            return False
        try:
            return bool(self._service.is_unlocked())
        except Exception:
            return False

    def active_session_count(self) -> int:
        """Returns the number of registered active sessions."""
        return len(self._sessions)

    def _lock_vault_if_unlocked(self) -> None:
        """Locks vault on service and purges master derived key."""
        try:
            if self._service is not None and self.is_vault_unlocked():
                self._service.lock_vault()
        finally:
            try:
                CodecUtils.clear_derived_key()
            except Exception:
                pass
