from __future__ import annotations

from typing import Set

from app.ports.refresh_token_repository import RefreshTokenRepository


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    """Repositório simples em memória usado por adapters e testes."""

    def __init__(self) -> None:
        self._revoked: Set[str] = set()

    def revoke(self, token: str) -> None:
        self._revoked.add(token)

    def is_revoked(self, token: str) -> bool:
        return token in self._revoked
