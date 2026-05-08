"""Testes do gate de admin em /admin/ping (US-13 T-13.6).

Exerce o pipeline real do get_current_user (sem dependency_override) para
cobrir os tres ramos: sem token (401), token sem scope admin (403), token
com scope admin (200).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.admin_router import router
from app.adapters.config.settings import settings
from app.adapters.jwt_token_provider import JwtTokenProvider

USER_ID = "usuario-123"


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
    """Provider que usa o settings global, para que o token gerado aqui
    seja decodavel pelo pipeline real do get_current_user."""
    return JwtTokenProvider(settings)


class TestAdminRouterPing:
    """Gate por scope na rota administrativa de demonstracao."""

    def test_admin_ping_sem_token_retorna_401(self, client: TestClient) -> None:
        """CT-13.6-01: sem Authorization header retorna 401."""
        response = client.get("/admin/ping")

        assert response.status_code == 401

    def test_admin_ping_com_token_user_retorna_403(
        self,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-13.6-02: token valido com scope 'user' (sem admin) retorna 403."""
        token = token_provider.generate_access_token(USER_ID, scopes=["user"])

        response = client.get(
            "/admin/ping",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    def test_admin_ping_com_token_sem_scopes_retorna_403(
        self,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-13.6-03: token valido com scopes=[] retorna 403."""
        token = token_provider.generate_access_token(USER_ID, scopes=[])

        response = client.get(
            "/admin/ping",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_admin_ping_com_token_admin_retorna_200(
        self,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-13.6-04: token com scope 'admin' acessa a rota e devolve 200."""
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        response = client.get(
            "/admin/ping",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == USER_ID

    def test_admin_ping_com_token_admin_e_user_retorna_200(
        self,
        client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        """CT-13.6-05: usuario com scopes=['admin', 'user'] (admin promovido)
        passa pelo gate. Garante que a checagem eh 'admin in scopes', nao
        'scopes == ['admin']'."""
        token = token_provider.generate_access_token(USER_ID, scopes=["admin", "user"])

        response = client.get(
            "/admin/ping",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_admin_ping_com_token_invalido_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-13.6-06: token malformado/assinatura invalida retorna 401
        (precede a checagem de scope)."""
        response = client.get(
            "/admin/ping",
            headers={"Authorization": "Bearer nao.eh.um.jwt.de.verdade"},
        )

        assert response.status_code == 401
