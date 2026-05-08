"""Testes do gate de admin em /admin/ping (US-13 T-13.6).

Exerce o pipeline real do get_current_user (sem dependency_override) para
cobrir os tres ramos: sem token (401), token sem scope admin (403), token
com scope admin (200).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.admin_router import router
from app.adapters.api.dependencies import get_user_service
from app.adapters.config.settings import settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.user_service import UserService
from app.domain.user import Email, HashedPassword, User, Username
from tests.fakes.access_level_repository import FakeAccessLevelRepository
from tests.fakes.user_repository import FakeUserRepository

USER_ID = "usuario-123"


def _make_test_user(seq: int) -> User:
    """Cria um User com id sequencial para ordenacao deterministica."""
    return User(
        id=f"user-{seq:04d}",
        username=Username(f"user.{seq:04d}"),
        email=Email(f"user{seq}@example.com"),
        hashed_password=HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        first_name="Test",
        last_name=f"User{seq}",
    )


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


class TestAdminListUsers:
    """Testes do endpoint GET /admin/users (US-14).

    Exerce o pipeline real do get_current_user (sem dependency_override) para
    cobrir o gate por scope. Apenas o get_user_service eh sobrescrito, para
    injetar um UserService com fakes em memoria.
    """

    @pytest.fixture
    def admin_repo(self) -> FakeUserRepository:
        """Fake repo populado com 5 users de teste com ids ordenaveis."""
        repo = FakeUserRepository()
        for i in range(1, 6):
            repo.save(_make_test_user(i))
        return repo

    @pytest.fixture
    def admin_app(
        self,
        app: FastAPI,
        admin_repo: FakeUserRepository,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> Iterator[FastAPI]:
        service = UserService(
            user_repo=admin_repo,
            access_level_repo=fake_access_level_repo,
        )
        app.dependency_overrides[get_user_service] = lambda: service
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    def admin_client(self, admin_app: FastAPI) -> TestClient:
        return TestClient(admin_app)

    # CT-14.R-01: sem Authorization header retorna 401 (gate)
    def test_sem_token_retorna_401(self, admin_client: TestClient) -> None:
        response = admin_client.get("/admin/users")

        assert response.status_code == 401

    # CT-14.R-02: token com scope user (sem admin) retorna 403 (gate)
    def test_com_token_user_retorna_403(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["user"])

        response = admin_client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    # CT-14.R-03: token admin retorna 200 com items e cursor (pagina inicial)
    def test_com_token_admin_retorna_200_com_items_e_cursor(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        response = admin_client.get(
            "/admin/users?limit=2",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 2
        assert body["next_cursor"] is not None

    # CT-14.R-04: cursor avanca para proxima pagina sem repetir items
    def test_cursor_avanca_para_proxima_pagina(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        primeira = admin_client.get(
            "/admin/users?limit=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        cursor = primeira.json()["next_cursor"]

        segunda = admin_client.get(
            f"/admin/users?limit=2&cursor={cursor}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert segunda.status_code == 200
        ids_primeira = {u["id"] for u in primeira.json()["items"]}
        ids_segunda = {u["id"] for u in segunda.json()["items"]}
        assert ids_primeira.isdisjoint(ids_segunda)

    # CT-14.R-05: fim da lista retorna next_cursor null
    def test_ultima_pagina_retorna_next_cursor_null(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        response = admin_client.get(
            "/admin/users?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["next_cursor"] is None

    # CT-14.R-06: limit fora do intervalo [1, 100] retorna 422 (Pydantic)
    def test_limit_fora_do_intervalo_retorna_422(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        response = admin_client.get(
            "/admin/users?limit=0",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    # CT-14.R-07: cursor inexistente retorna 400 (domain exception)
    def test_cursor_inexistente_retorna_400(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        response = admin_client.get(
            "/admin/users?cursor=uuid-inexistente",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    # CT-14.R-08: senha nunca eh exposta no response
    def test_response_nao_expoe_hashed_password(
        self,
        admin_client: TestClient,
        token_provider: JwtTokenProvider,
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        response = admin_client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        for item in response.json()["items"]:
            assert "password" not in item
            assert "hashed_password" not in item
