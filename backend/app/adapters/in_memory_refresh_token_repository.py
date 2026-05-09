from __future__ import annotations

from typing import Dict, Set

from app.ports.refresh_token_repository import RefreshTokenRepository


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    """Repositório simples em memória usado por adapters e testes."""

    def __init__(self) -> None:
        self._revoked: Set[str] = set()
        self._user_tokens: Dict[str, Set[str]] = {}  # user_id -> {tokens}

    def revoke(self, token: str) -> None:
        self._revoked.add(token)

    def is_revoked(self, token: str) -> bool:
        return token in self._revoked

    def revoke_all_by_user(self, user_id: str) -> None:
        """Revoga todos os refresh tokens ativos de um usuário (idempotente)."""
        if user_id in self._user_tokens:
            self._revoked.update(self._user_tokens[user_id])

    def register_token_for_user(self, user_id: str, token: str) -> None:
        """Registra associação entre user_id e token (para testes)."""
        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = set()
        self._user_tokens[user_id].add(token)

