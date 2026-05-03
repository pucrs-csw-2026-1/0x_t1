from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.auth_router import _get_auth_service, router
from app.adapters.config.settings import Settings
from app.adapters.in_memory_refresh_token_repository import InMemoryRefreshTokenRepository
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService


class SpyAuthService(AuthService):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def logout(self, refresh_token: str) -> None:
        self.calls.append(refresh_token)


def _make_client(auth_service: SpyAuthService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_get_auth_service] = lambda: auth_service
    return TestClient(app)


def _make_access_token() -> str:
    settings = Settings(  # type: ignore[call-arg]
        secret_key="changeme",
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )
    provider = JwtTokenProvider(settings)
    return provider.generate_access_token("usuario-123", ["user"])


def test_logout_requer_bearer_token_retorna_401() -> None:
    client = _make_client(SpyAuthService())

    response = client.post("/auth/logout", json={"refresh_token": "refresh-token"})

    assert response.status_code == 401


def test_logout_com_bearer_token_chama_servico() -> None:
    auth_service = SpyAuthService()
    client = _make_client(auth_service)
    access_token = _make_access_token()

    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": "refresh-token-ativo"},
    )

    assert response.status_code == 204
    assert auth_service.calls == ["refresh-token-ativo"]
