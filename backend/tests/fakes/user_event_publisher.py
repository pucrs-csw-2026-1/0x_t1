from __future__ import annotations

from app.domain.user import User
from app.ports.user_event_publisher import UserEventPublisher


class SpyUserEventPublisher(UserEventPublisher):
    """Spy: registra os usuários publicados para verificação nos testes."""

    def __init__(self) -> None:
        self.published: list[User] = []

    def publish_profile_changed(self, user: User) -> None:
        self.published.append(user)


class FailingUserEventPublisher(UserEventPublisher):
    """Stub que sempre falha — usado para exercitar a política best-effort."""

    def publish_profile_changed(self, user: User) -> None:
        raise RuntimeError("SNS indisponível")
