from abc import ABC, abstractmethod
from typing import Optional

from dev.abhishekraha.secretmanager.model.Secret import Secret


class VaultDataProvider(ABC):
    """Abstract interface defining required vault operations for local and remote data providers."""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the underlying vault storage or client environment."""
        ...

    @abstractmethod
    def is_initialized(self) -> bool:
        """Check whether the vault is initialized."""
        ...

    @abstractmethod
    def is_unlocked(self) -> bool:
        """Check whether the vault is currently unlocked."""
        ...

    @abstractmethod
    def setup_master_password(self, master_password: str, confirmation_password: str) -> None:
        """Set up master password for a fresh vault."""
        ...

    @abstractmethod
    def authenticate(self, master_password: str) -> tuple[bool, str]:
        """Authenticate against the vault using master password."""
        ...

    @abstractmethod
    def lock_vault(self) -> None:
        """Lock the vault and zero out active session/keys."""
        ...

    @abstractmethod
    def get_lockout_status(self) -> dict:
        """Return the current lockout state and remaining duration."""
        ...

    @abstractmethod
    def change_master_password(self, current_password: str, new_password: str, confirmation_password: str) -> None:
        """Change the vault master password."""
        ...

    @abstractmethod
    def get_secret_records(self, filter_text: str = "") -> list[Secret]:
        """Retrieve full secret records matching filter_text."""
        ...

    @abstractmethod
    def get_secret_names(self, filter_text: str = "") -> list[str]:
        """Retrieve names of secrets matching filter_text."""
        ...

    @abstractmethod
    def get_secret(self, name: str) -> Optional[Secret]:
        """Retrieve a specific secret by name."""
        ...

    @abstractmethod
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
        """Add a new secret to the vault."""
        ...

    @abstractmethod
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
        """Update an existing secret in the vault."""
        ...

    @abstractmethod
    def delete_secret(self, name: str) -> None:
        """Delete a secret by name."""
        ...

    @abstractmethod
    def generate_password(self, length: int = 20) -> str:
        """Generate a cryptographically secure random password."""
        ...

    @abstractmethod
    def audit_health(self) -> dict:
        """Perform a security and health audit across vault credentials."""
        ...
