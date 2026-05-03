from abc import ABC, abstractmethod


class RefreshTokenRepository(ABC):
    """Port para persistência do estado de revogação de refresh tokens."""

    @abstractmethod
    def revoke(self, token: str) -> None:
        ...

    @abstractmethod
    def is_revoked(self, token: str) -> bool:
        ...
