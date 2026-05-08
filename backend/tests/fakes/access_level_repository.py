from __future__ import annotations

from app.domain.access_level import AccessLevel
from app.ports.access_level_repository import AccessLevelRepository


class FakeAccessLevelRepository(AccessLevelRepository):
    """Implementacao em memoria do AccessLevelRepository para testes."""

    def __init__(self, levels: list[AccessLevel] | None = None) -> None:
        self._by_id: dict[str, AccessLevel] = {}
        for level in levels or []:
            self._by_id[level.id] = level

    def find_by_id(self, id: str) -> AccessLevel | None:
        return self._by_id.get(id)

    def find_by_title(self, title: str) -> AccessLevel | None:
        return next(
            (level for level in self._by_id.values() if level.title == title),
            None,
        )
