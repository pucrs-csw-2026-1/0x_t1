"""Testes de integração para auth_router (US-07)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.adapters.api.auth_router import router
from app.adapters.config.settings import Settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.domain.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)

SECRET = "chave-secreta-de-teste"
ALGORITHM = "HS256"
USER_ID = "usuario-123"
SCOPES = ["user:read", "user:write"]


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        secret_key=SECRET,
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


class TestAuthRouter:
    # CT-01: POST /auth/refresh com token válido retorna 200
    def test_refresh_token_valido_retorna_200_com_access_token(
        self,
        app: FastAPI,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        from app.adapters.api.dependencies import get_auth_service
        from app.application.auth_service import AuthService

        refresh_token = token_provider.generate_refresh_token(USER_ID)
        mock_service = MagicMock(spec=AuthService)
        mock_service.refresh.return_value = token_provider.generate_access_token(
            USER_ID, SCOPES
        )

        app.dependency_overrides[get_auth_service] = lambda: mock_service

        response = client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Valida que o token retornado é um access token válido
        payload = token_provider.decode_token(data["access_token"])
        assert payload["sub"] == USER_ID

    # CT-02: POST /auth/refresh com token expirado retorna 401
    def test_refresh_token_expirado_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        from app.adapters.api.dependencies import get_auth_service
        from app.application.auth_service import AuthService

        mock_service = MagicMock(spec=AuthService)
        mock_service.refresh.side_effect = TokenExpiredError()
        app.dependency_overrides[get_auth_service] = lambda: mock_service

        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        refresh_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

        response = client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        data = response.json()
        assert "Refresh token expirado" in data["detail"]
        assert "WWW-Authenticate" in response.headers

    # CT-03: POST /auth/refresh com token revogado retorna 401
    def test_refresh_token_revogado_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        from app.adapters.api.dependencies import get_auth_service
        from app.application.auth_service import AuthService

        mock_service = MagicMock(spec=AuthService)
        mock_service.refresh.side_effect = TokenRevokedError()
        app.dependency_overrides[get_auth_service] = lambda: mock_service

        revoked_payload: dict[str, Any] = {
            "sub": USER_ID,
            "revoked": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        refresh_token = jwt.encode(revoked_payload, SECRET, algorithm=ALGORITHM)

        response = client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        data = response.json()
        assert "Refresh token revogado" in data["detail"]
        assert "WWW-Authenticate" in response.headers

    # CT-04: POST /auth/refresh com assinatura adulterada retorna 401
    def test_refresh_token_assinatura_adulterada_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        from app.adapters.api.dependencies import get_auth_service
        from app.application.auth_service import AuthService

        mock_service = MagicMock(spec=AuthService)
        mock_service.refresh.side_effect = InvalidTokenError()
        app.dependency_overrides[get_auth_service] = lambda: mock_service

        adulterado = "token.falso.assinatura_invalida"

        response = client.post(
            "/auth/refresh", json={"refresh_token": adulterado}
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        data = response.json()
        assert "Refresh token inválido" in data["detail"]
        assert "WWW-Authenticate" in response.headers

    # CT-05: POST /auth/refresh com payload sem sub retorna 401
    def test_refresh_token_sem_sub_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        from app.adapters.api.dependencies import get_auth_service
        from app.application.auth_service import AuthService

        mock_service = MagicMock(spec=AuthService)
        mock_service.refresh.side_effect = InvalidTokenError()
        app.dependency_overrides[get_auth_service] = lambda: mock_service

        payload_sem_sub: dict[str, Any] = {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        refresh_token = jwt.encode(payload_sem_sub, SECRET, algorithm=ALGORITHM)

        response = client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        data = response.json()
        assert "Refresh token inválido" in data["detail"]
        assert "WWW-Authenticate" in response.headers
