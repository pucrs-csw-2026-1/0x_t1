"""Testes de integracao para user_router."""

from __future__ import annotations

from unittest.mock import create_autospec

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.adapters.api.user_router import router
from app.application.user_service import UserService
from app.domain.user import User


class TestUserRouter:
    def test_get_me_retorna_dados_do_usuario_autenticado(self, valid_user: User) -> None:
        app = FastAPI()
        app.include_router(router)

        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.get_user_by_id.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        client = TestClient(app)
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
