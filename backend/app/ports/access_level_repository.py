from abc import ABC, abstractmethod

from app.domain.access_level import AccessLevel


class AccessLevelRepository(ABC):
    """Port para repositório de níveis de acesso."""

    @abstractmethod
    def find_by_id(self, id: str) -> AccessLevel | None: ...

    @abstractmethod
    def find_by_title(self, title: str) -> AccessLevel | None: ...
