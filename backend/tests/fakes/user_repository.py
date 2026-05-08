from __future__ import annotations

from app.domain.user import Email, User, Username
from app.ports.user_repository import UserPage, UserRepository


class FakeUserRepository(UserRepository):
    """Implementacao em memoria do UserRepository para testes."""

    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}

    def save(self, user: User) -> User:
        self._by_id[user.id] = user
        return user

    def find_by_id(self, id: str) -> User | None:
        return self._by_id.get(id)

    def find_by_email(self, email: Email) -> User | None:
        return next((u for u in self._by_id.values() if u.email == email), None)

    def find_by_username(self, username: Username) -> User | None:
        return next((u for u in self._by_id.values() if u.username == username), None)

    def find_all(self, limit: int, cursor: str | None = None) -> UserPage:
        # Ordem por id garante paginacao deterministica.
        ordenados = sorted(self._by_id.values(), key=lambda u: u.id)
        if cursor is not None:
            ordenados = [u for u in ordenados if u.id > cursor]
        items = ordenados[:limit]
        tem_mais = len(ordenados) > limit
        next_cursor = items[-1].id if (tem_mais and items) else None
        return UserPage(items=items, next_cursor=next_cursor)
