"""Testes de integração para auth_router (US-06 login, US-08 logout, US-11 proteção)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import create_autospec

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.adapters.api.auth_router import router
from app.adapters.api.dependencies import (
    get_auth_service,
    get_current_user,
)
from app.adapters.config.settings import Settings, read_key
from app.adapters.config.settings import settings as global_settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.domain.exceptions import (
    InvalidClientError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)

ALGORITHM = "RS256"
USER_ID = "usuario-123"
SCOPES = ["user:read", "user:write"]
PRIVATE_KEY = read_key("keys/dev_private.pem")


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
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


@pytest.fixture
def global_token_provider() -> JwtTokenProvider:
    """Provider que usa o settings global — gera tokens decodáveis pelo
    pipeline real do get_current_user (sem override de dependency)."""
    return JwtTokenProvider(global_settings)


class TestAuthRouterLogin:
    """Testes do endpoint POST /auth/login."""

    def test_login_com_credenciais_validas_retorna_200(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-01: Login com credenciais válidas retorna 200 com tokens."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.login.return_value = {
            "access_token": "access.jwt",
            "refresh_token": "refresh.jwt",
            "token_type": "bearer",
        }
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        response = client.post(
            "/auth/login",
            data={"username": "maria@example.com", "password": "Senha@123"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access.jwt"
        assert data["refresh_token"] == "refresh.jwt"
        assert data["token_type"] == "bearer"

    def test_login_com_credenciais_invalidas_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-02: Login com credenciais inválidas retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.login.side_effect = InvalidCredentialsError()
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        response = client.post(
            "/auth/login",
            data={"username": "maria@example.com", "password": "SenhaErrada@1"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert response.json()["detail"] == "Credenciais inválidas."
        assert response.headers["www-authenticate"] == "Bearer"

    def test_login_com_email_malformado_retorna_401_credenciais_invalidas(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-02b: email malformado vira 401 'Credenciais inválidas' (não vaza
        formato/existência do usuário)."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.login.side_effect = InvalidCredentialsError()
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        response = client.post(
            "/auth/login",
            data={"username": "nao-eh-email", "password": "Senha@123"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert response.json()["detail"] == "Credenciais inválidas."
        assert response.headers["www-authenticate"] == "Bearer"


class TestAuthRouterRefresh:
    """Testes do endpoint POST /auth/refresh."""

    def test_refresh_com_token_valido_retorna_200(
        self,
        app: FastAPI,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-03: Refresh com token válido retorna 200 com novo access token."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        new_access_token = token_provider.generate_access_token(USER_ID, SCOPES)
        auth_service_mock.refresh.return_value = new_access_token
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        refresh_token = token_provider.generate_refresh_token(USER_ID)

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_com_token_expirado_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-04: Refresh com token expirado retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.refresh.side_effect = TokenExpiredError()
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        refresh_token = jwt.encode(expired_payload, PRIVATE_KEY, algorithm=ALGORITHM)

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert "Refresh token expirado" in response.json()["detail"]
        assert "WWW-Authenticate" in response.headers

    def test_refresh_com_token_revogado_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-05: Refresh com token revogado retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.refresh.side_effect = TokenRevokedError()
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        revoked_payload: dict[str, Any] = {
            "sub": USER_ID,
            "revoked": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        refresh_token = jwt.encode(revoked_payload, PRIVATE_KEY, algorithm=ALGORITHM)

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert "Refresh token revogado" in response.json()["detail"]
        assert "WWW-Authenticate" in response.headers

    def test_refresh_com_token_assinatura_invalida_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-06: Refresh com assinatura inválida retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.refresh.side_effect = InvalidTokenError()
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        refresh_token = "token.falso.assinatura_invalida"

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert "Refresh token inválido" in response.json()["detail"]
        assert "WWW-Authenticate" in response.headers


class TestAuthRouterLogout:
    """Testes do endpoint POST /auth/logout."""

    def test_logout_com_usuario_autenticado_retorna_204(
        self,
        app: FastAPI,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-07: Logout com usuário autenticado retorna 204."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock
        app.dependency_overrides[get_current_user] = lambda: USER_ID

        refresh_token = token_provider.generate_refresh_token(USER_ID)

        response = client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 204
        auth_service_mock.logout.assert_called_once_with(refresh_token)

    def test_logout_sem_bearer_token_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-08: Logout sem token de autenticação retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        refresh_token = token_provider.generate_refresh_token(USER_ID)

        response = client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401


class TestAuthRouterLogoutAuthProtection:
    """Testes end-to-end da proteção JWT em POST /auth/logout (US-11).

    Não sobrescreve get_current_user — exerce o pipeline real para cobrir
    a tabela de decisão exigida nos critérios de aceite.
    """

    def test_logout_com_token_valido_retorna_204(
        self,
        app: FastAPI,
        client: TestClient,
        global_token_provider: JwtTokenProvider,
    ) -> None:
        """CT-09: logout com Bearer token válido decodifica e chama logout."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        access_token = global_token_provider.generate_access_token(
            USER_ID, scopes=["user"]
        )
        refresh_token = global_token_provider.generate_refresh_token(USER_ID)

        response = client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 204
        auth_service_mock.logout.assert_called_once_with(refresh_token)

    def test_logout_com_token_expirado_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-10: logout com access token expirado retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "scopes": ["user"],
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        access_token = jwt.encode(
            expired_payload,
            PRIVATE_KEY,
            algorithm="RS256",
        )

        response = client.post(
            "/auth/logout",
            json={"refresh_token": "qualquer.refresh.token"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert response.json()["detail"] == "Token expirado."
        auth_service_mock.logout.assert_not_called()

    def test_logout_com_token_assinatura_invalida_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-11: logout com access token assinado com chave errada retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        payload: dict[str, Any] = {
            "sub": USER_ID,
            "scopes": ["user"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        access_token = jwt.encode(payload, "chave-de-atacante-hs256", algorithm="HS256")

        response = client.post(
            "/auth/logout",
            json={"refresh_token": "qualquer.refresh.token"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido."
        auth_service_mock.logout.assert_not_called()


class TestAuthRouterClientCredentials:
    """Testes do endpoint POST /auth/token (US-28 parte 2)."""

    def test_client_credentials_valido_retorna_200(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-CC-01: client_id/secret válidos retornam 200 com token de serviço."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.issue_service_token.return_value = {
            "access_token": "svc.jwt",
            "token_type": "bearer",
        }
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        response = client.post(
            "/auth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "metrics-service",
                "client_secret": "dev-metrics-secret",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "svc.jwt"
        assert data["token_type"] == "bearer"
        assert "refresh_token" not in data
        auth_service_mock.issue_service_token.assert_called_once_with(
            "metrics-service", "dev-metrics-secret"
        )

    def test_credenciais_de_cliente_invalidas_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-CC-02: client_secret errado / cliente desconhecido retorna 401."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        auth_service_mock.issue_service_token.side_effect = InvalidClientError()
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        response = client.post(
            "/auth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "metrics-service",
                "client_secret": "errado",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    def test_grant_type_nao_suportado_retorna_400(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-CC-03: grant_type diferente de client_credentials retorna 400."""
        auth_service_mock = create_autospec(AuthService, instance=True)
        app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

        response = client.post(
            "/auth/token",
            data={
                "grant_type": "password",
                "client_id": "metrics-service",
                "client_secret": "dev-metrics-secret",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert response.json()["detail"] == "unsupported_grant_type"
        auth_service_mock.issue_service_token.assert_not_called()
