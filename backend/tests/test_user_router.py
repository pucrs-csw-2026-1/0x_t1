"""Testes de integração para user_router."""

from __future__ import annotations

from unittest.mock import create_autospec

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.adapters.api.user_router import router
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
        assert data["is_active"] is valid_user.is_active
        user_service_mock.get_user_by_id.assert_called_once_with(valid_user.id)

    def test_get_me_sem_bearer_token_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-02: GET /users/me sem token retorna 401."""
        response = client.get("/users/me")

        assert response.status_code == 401

