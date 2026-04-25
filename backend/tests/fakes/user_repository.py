from __future__ import annotations

from app.domain.user import Email, User, Username
from app.ports.user_repository import UserRepository


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
