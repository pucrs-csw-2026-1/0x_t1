from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.adapters.api.user_router import router
from app.domain.user import Email, HashedPassword, User, Username


class StubUserService:
    def __init__(self, user: User) -> None:
        self._user = user

    def get_user_by_id(self, user_id: str) -> User:
        assert user_id == self._user.id
        return self._user


def _make_user() -> User:
    return User(
        id="usuario-123",
        username=Username("maria.silva"),
        email=Email("maria@example.com"),
        hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        first_name="Maria",
        last_name="Silva",
        access_level=["user"],
        is_active=True,
        created_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
    )


def _make_client(user_service: StubUserService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user_service._user.id
    app.dependency_overrides[get_user_service] = lambda: user_service
    return TestClient(app)


def test_get_me_retorna_usuario_autenticado() -> None:
    user = _make_user()
    client = _make_client(StubUserService(user))

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == user.id
    assert response.json()["email"] == user.email.value
    assert response.json()["username"] == user.username.value


def test_get_me_sem_bearer_token_retorna_401() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 401
