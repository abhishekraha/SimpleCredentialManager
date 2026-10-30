from typing import Optional

from dev.abhishekraha.secretmanager.core.PasswordHealthService import PasswordHealthService
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.core.VaultDataProvider import VaultDataProvider
from dev.abhishekraha.secretmanager.model.Secret import Secret


class LocalVaultProvider(VaultDataProvider):
    """Local vault data provider wrapping SecretManagerService."""

    def __init__(self, service: Optional[SecretManagerService] = None) -> None:
        self.service = service or SecretManagerService(client_name="desktop-local-provider")

    def initialize(self) -> bool:
        return self.service.initialize()

    def is_initialized(self) -> bool:
        return self.service.is_initialized()

    def is_unlocked(self) -> bool:
        return self.service.is_unlocked()

    def setup_master_password(self, master_password: str, confirmation_password: str) -> None:
        self.service.setup_master_password(master_password, confirmation_password)

    def authenticate(self, master_password: str) -> tuple[bool, str]:
        return self.service.authenticate(master_password)

    def lock_vault(self) -> None:
        self.service.lock_vault()

    def get_lockout_status(self) -> dict:
        return self.service.get_lockout_status()

    def change_master_password(self, current_password: str, new_password: str, confirmation_password: str) -> None:
        self.service.change_master_password(current_password, new_password, confirmation_password)

    def get_secret_records(self, filter_text: str = "") -> list[Secret]:
        return self.service.get_secret_records(filter_text)

    def get_secret_names(self, filter_text: str = "") -> list[str]:
        return self.service.get_secret_names(filter_text)

    def get_secret(self, name: str) -> Optional[Secret]:
        return self.service.get_secret(name)

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
        self.service.add_secret(
            name=name,
            username=username,
            password=password,
            url=url,
            comments=comments,
            category=category,
            is_favorite=is_favorite,
            totp_secret=totp_secret,
            tags=tags,
        )

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
        self.service.update_secret(
            original_name=original_name,
            new_name=new_name,
            username=username,
            password=password,
            url=url,
            comments=comments,
            category=category,
            is_favorite=is_favorite,
            totp_secret=totp_secret,
            tags=tags,
        )

    def delete_secret(self, name: str) -> None:
        self.service.delete_secret(name)

    def generate_password(self, length: int = 20) -> str:
        return self.service.generate_password(length)

    def audit_health(self) -> dict:
        records = self.get_secret_records()
        return PasswordHealthService().audit_vault(records)
