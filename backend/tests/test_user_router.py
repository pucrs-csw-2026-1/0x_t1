"""Testes de integração para user_router."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import create_autospec

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.adapters.api.user_router import router
from app.adapters.config.settings import Settings, settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.user_service import UserService
from app.domain.user import User


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def token_provider() -> JwtTokenProvider:
    """Provider que usa o mesmo settings global que get_current_user vai usar."""
    return JwtTokenProvider(settings)


class TestUserRouter:
    """Testes do endpoint GET /users/me."""

    def test_get_me_retorna_dados_do_usuario_autenticado(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        """CT-01: GET /users/me com token válido retorna dados do usuário."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.get_user_by_id.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.get("/users/me")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == valid_user.id
        assert data["first_name"] == valid_user.first_name
        assert data["last_name"] == valid_user.last_name
        assert data["username"] == valid_user.username.value
        assert data["email"] == valid_user.email.value
        assert data["access_level"] == valid_user.access_level
        assert data["is_active"] is valid_user.is_active
        assert "created_at" in data
        user_service_mock.get_user_by_id.assert_called_once_with(valid_user.id)

    def test_get_me_sem_bearer_token_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-02: GET /users/me sem token retorna 401."""
        response = client.get("/users/me")

        assert response.status_code == 401


class TestUserRouterAuthProtection:
    """Testes end-to-end da proteção JWT em GET /users/me (US-11).

    Diferente de TestUserRouter, NÃO sobrescreve get_current_user — exerce
    o pipeline real de validação para cobrir a tabela de decisão exigida
    pelos critérios de aceite: token ausente, inválido, expirado, válido.
    """

    def test_token_valido_retorna_200_com_user_id_correto(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-03: pipeline real decodifica token e injeta o user_id correto."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.get_user_by_id.return_value = valid_user
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        token = token_provider.generate_access_token(valid_user.id, scopes=["user"])

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["id"] == valid_user.id
        user_service_mock.get_user_by_id.assert_called_once_with(valid_user.id)

    def test_token_expirado_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-04: token com exp no passado retorna 401."""
        expired_payload: dict[str, Any] = {
            "sub": "user-123",
            "scopes": ["user"],
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(
            expired_payload, settings.secret_key, algorithm=settings.algorithm
        )

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token expirado."
        assert response.headers["www-authenticate"] == "Bearer"

    def test_token_assinatura_invalida_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-05: token assinado com chave diferente retorna 401."""
        outra_chave = "chave-de-atacante-diferente-do-servidor"
        payload: dict[str, Any] = {
            "sub": "user-123",
            "scopes": ["user"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, outra_chave, algorithm=settings.algorithm)

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido."
        assert response.headers["www-authenticate"] == "Bearer"

    def test_token_sem_claim_sub_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-06: token bem assinado mas sem claim 'sub' retorna 401."""
        payload: dict[str, Any] = {
            "scopes": ["user"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token inválido."

    def test_token_malformado_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-07: header com string não-JWT retorna 401."""
        response = client.get(
            "/users/me",
            headers={"Authorization": "Bearer nao.eh.um.jwt.de.verdade"},
        )

        assert response.status_code == 401

    def test_token_assinado_com_outro_algoritmo_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-08: token assinado com algoritmo diferente do esperado retorna 401."""
        outras_settings = Settings(  # type: ignore[call-arg]
            secret_key=settings.secret_key,
            algorithm="HS512",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
        )
        outro_provider = JwtTokenProvider(outras_settings)
        token = outro_provider.generate_access_token("user-123", scopes=["user"])

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
