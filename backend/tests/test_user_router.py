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
from app.domain.access_level import AccessLevel
from app.domain.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidNameError,
    InvalidUsernameError,
    SamePasswordError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.user import User
from tests.conftest import ADMIN_UUID, USER_UUID
from tests.fakes.access_level_repository import FakeAccessLevelRepository
from tests.fakes.user_repository import FakeUserRepository


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

    def test_get_me_usuario_inexistente_retorna_404(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-02b: GET /users/me com user_id válido no token mas usuário
        removido do banco retorna 404 (não 500)."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.get_user_by_id.side_effect = UserNotFoundError(
            "user-deletado"
        )

        app.dependency_overrides[get_current_user] = lambda: "user-deletado"
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.get("/users/me")

        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "user-deletado" in response.json()["detail"]


class TestUserRouterRegister:
    """Testes do endpoint POST /users/register — tratamento de erros."""

    def test_register_com_dados_validos_retorna_201(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        """CT-REG-01: register com payload válido retorna 201."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.register.return_value = valid_user
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.post(
            "/users/register",
            json={
                "first_name": "Maria",
                "last_name": "Silva",
                "username": "maria.silva",
                "email": "maria@example.com",
                "password": "Senha@123",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 201
        assert response.json()["email"] == valid_user.email.value

    def test_register_com_email_duplicado_retorna_409(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-REG-02: email já cadastrado retorna 409 (não 500)."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.register.side_effect = EmailAlreadyExistsError(
            "maria@example.com"
        )
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.post(
            "/users/register",
            json={
                "first_name": "Maria",
                "last_name": "Silva",
                "username": "maria.silva",
                "email": "maria@example.com",
                "password": "Senha@123",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 409
        assert "maria@example.com" in response.json()["detail"]

    def test_register_com_email_invalido_retorna_400(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-REG-03: email malformado retorna 400 (não 500)."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.register.side_effect = InvalidEmailError("nao-eh-email")
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.post(
            "/users/register",
            json={
                "first_name": "Maria",
                "last_name": "Silva",
                "username": "maria.silva",
                "email": "nao-eh-email",
                "password": "Senha@123",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "nao-eh-email" in response.json()["detail"]

    def test_register_com_senha_fraca_retorna_400(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-REG-04: senha fraca retorna 400 (não 500)."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.register.side_effect = WeakPasswordError(
            "deve ter ao menos 8 caracteres"
        )
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.post(
            "/users/register",
            json={
                "first_name": "Maria",
                "last_name": "Silva",
                "username": "maria.silva",
                "email": "maria@example.com",
                "password": "abc",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "Senha fraca" in response.json()["detail"]

    def test_register_com_username_invalido_retorna_400(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-REG-05: username inválido retorna 400 (não 500)."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.register.side_effect = InvalidUsernameError(
            "username deve ter ao menos 8 caracteres"
        )
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.post(
            "/users/register",
            json={
                "first_name": "Maria",
                "last_name": "Silva",
                "username": "abc",
                "email": "maria@example.com",
                "password": "Senha@123",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()


class TestUserRouterRegisterAccessLevelDiscard:
    """US-13: register publico nunca concede perfis elevados.

    Critério de aceite: tentativa de auto-promocao via access_level no body
    deve ser silenciosamente descartada e o usuario criado sempre com 'user'.
    Cobre as 3 particoes: sem campo, lista vazia, payload com 'admin'.
    """

    def _post_register(
        self,
        app: FastAPI,
        client: TestClient,
        body: dict[str, object],
    ) -> tuple[int, dict[str, object]]:
        """Roda POST /users/register usando UserService real com fakes,
        para que access_level do response reflita o que o service decidiu."""
        fake_user_repo = FakeUserRepository()
        fake_access_level_repo = FakeAccessLevelRepository(
            levels=[
                AccessLevel(id=ADMIN_UUID, title="admin"),
                AccessLevel(id=USER_UUID, title="user"),
            ]
        )
        service = UserService(
            user_repo=fake_user_repo,
            access_level_repo=fake_access_level_repo,
        )

        app.dependency_overrides[get_user_service] = lambda: service

        response = client.post("/users/register", json=body)

        app.dependency_overrides.clear()
        return response.status_code, response.json()

    def test_register_sem_access_level_cria_como_user(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-13.4-01: payload sem access_level cria com perfil 'user'."""
        status_code, body = self._post_register(
            app,
            client,
            {
                "first_name": "Joao",
                "last_name": "Silva",
                "username": "joao.silva",
                "email": "joao@example.com",
                "password": "S3nh@Forte!",
            },
        )

        assert status_code == 201
        assert body["access_level"] == [USER_UUID]

    def test_register_com_access_level_vazio_cria_como_user(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-13.4-02: payload com access_level=[] cria com perfil 'user'."""
        status_code, body = self._post_register(
            app,
            client,
            {
                "first_name": "Joao",
                "last_name": "Silva",
                "username": "joao.silva",
                "email": "joao@example.com",
                "password": "S3nh@Forte!",
                "access_level": [],
            },
        )

        assert status_code == 201
        assert body["access_level"] == [USER_UUID]

    def test_register_com_admin_no_payload_eh_silenciosamente_descartado(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-13.4-03: payload com access_level=[ADMIN_UUID] (auto-promocao)
        eh aceito sem 422 mas o usuario eh criado como 'user'."""
        status_code, body = self._post_register(
            app,
            client,
            {
                "first_name": "Joao",
                "last_name": "Silva",
                "username": "joao.silva",
                "email": "joao@example.com",
                "password": "S3nh@Forte!",
                "access_level": [ADMIN_UUID],
            },
        )

        assert status_code == 201
        assert body["access_level"] == [USER_UUID]
        assert ADMIN_UUID not in body["access_level"]


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


class TestUserRouterDeactivate:
    """Testes do endpoint DELETE /users/me (US-17)."""

    def test_delete_me_retorna_204_e_desativa_conta(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        """CT-01: DELETE /users/me com token válido retorna 204 e desativa a conta."""
        user_service_mock = create_autospec(UserService, instance=True)
        deactivated_user = valid_user
        deactivated_user.deactivate()
        user_service_mock.deactivate.return_value = deactivated_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.delete("/users/me")

        app.dependency_overrides.clear()

        assert response.status_code == 204
        assert response.text == ""
        user_service_mock.deactivate.assert_called_once_with(valid_user.id)

    def test_delete_me_sem_token_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        """CT-02: DELETE /users/me sem token retorna 401."""
        response = client.delete("/users/me")

        assert response.status_code == 401

    def test_delete_me_usuario_inexistente_retorna_404(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """CT-03: DELETE /users/me com user_id válido no token mas usuário
        inexistente retorna 404."""
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.deactivate.side_effect = UserNotFoundError("user-deletado")

        app.dependency_overrides[get_current_user] = lambda: "user-deletado"
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.delete("/users/me")

        app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_delete_me_idempotente_segunda_chamada_retorna_204(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        """CT-04: Chamar DELETE /users/me duas vezes retorna 204 ambas
        (idempotente — desativar um usuário já inativo não falha)."""
        user_service_mock = create_autospec(UserService, instance=True)
        deactivated_user = valid_user
        deactivated_user.deactivate()
        user_service_mock.deactivate.return_value = deactivated_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        # Primeira chamada
        response1 = client.delete("/users/me")
        # Segunda chamada
        response2 = client.delete("/users/me")

        app.dependency_overrides.clear()

        assert response1.status_code == 204
        assert response2.status_code == 204
        assert user_service_mock.deactivate.call_count == 2

    def test_delete_me_retorna_mesmo_204_se_ja_inativo(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        """CT-05: DELETE /users/me em usuário já inativo retorna 204
        (sem diferenciação de estado)."""
        user_service_mock = create_autospec(UserService, instance=True)
        already_inactive = valid_user
        already_inactive.deactivate()
        user_service_mock.deactivate.return_value = already_inactive

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.delete("/users/me")

        app.dependency_overrides.clear()

        assert response.status_code == 204


class TestUserRouterUpdateProfile:
    """Testes do endpoint PATCH /users/me (US-15)."""

    # CT-15.R01 (CA-01): dados válidos retornam 200 com perfil atualizado
    def test_patch_me_dados_validos_retorna_200(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"first_name": "Joana"})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == valid_user.id
        assert "password" not in data
        assert "hashed_password" not in data
        user_service_mock.update_profile.assert_called_once_with(
            user_id=valid_user.id,
            first_name="Joana",
            last_name=None,
            email=None,
            username=None,
        )

    # CT-15.R02 (CA-07): sem token retorna 401
    def test_patch_me_sem_token_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        response = client.patch("/users/me", json={"first_name": "Joana"})

        assert response.status_code == 401

    # CT-15.R03 (CA-03): email duplicado retorna 409
    def test_patch_me_email_duplicado_retorna_409(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.side_effect = EmailAlreadyExistsError(
            "outro@example.com"
        )

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"email": "outro@example.com"})

        app.dependency_overrides.clear()

        assert response.status_code == 409
        assert "outro@example.com" in response.json()["detail"]

    # CT-15.R04 (CA-04): username duplicado retorna 409
    def test_patch_me_username_duplicado_retorna_409(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.side_effect = UsernameAlreadyExistsError(
            "outro.usuario"
        )

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"username": "outro.usuario"})

        app.dependency_overrides.clear()

        assert response.status_code == 409
        assert "outro.usuario" in response.json()["detail"]

    # CT-15.R05 (CA-05): email inválido retorna 422
    def test_patch_me_email_invalido_retorna_422(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.side_effect = InvalidEmailError("nao-e-email")

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"email": "nao-e-email"})

        app.dependency_overrides.clear()

        assert response.status_code == 422

    # CT-15.R06 (CA-06): username inválido retorna 422
    def test_patch_me_username_invalido_retorna_422(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.side_effect = InvalidUsernameError(
            "username deve ter ao menos 8 caracteres"
        )

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"username": "curto"})

        app.dependency_overrides.clear()

        assert response.status_code == 422

    # CT-15.R07 (CA-09): nome inválido retorna 422
    def test_patch_me_nome_invalido_retorna_422(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.side_effect = InvalidNameError(
            "first_name não pode ser vazio"
        )

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"first_name": "   "})

        app.dependency_overrides.clear()

        assert response.status_code == 422

    # CT-15.R08 (CA-08): senha não é aceita no payload — campo ignorado pelo schema
    def test_patch_me_senha_nao_aparece_no_schema(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch(
            "/users/me",
            json={"first_name": "Joana", "password": "NovaS3nh@!"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        call_kwargs = user_service_mock.update_profile.call_args.kwargs
        assert "password" not in call_kwargs

    # CT-15.R09 (CA-08 / CA-09): access_level e is_active ignorados pelo schema
    def test_patch_me_access_level_e_is_active_nao_aceitos(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch(
            "/users/me",
            json={"access_level": ["admin-uuid"], "is_active": False},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        call_kwargs = user_service_mock.update_profile.call_args.kwargs
        assert "access_level" not in call_kwargs
        assert "is_active" not in call_kwargs

    # CT-15.R10 (CA-10): payload vazio é aceito — chama update_profile com todos None
    def test_patch_me_payload_vazio_retorna_200(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        user_service_mock.update_profile.assert_called_once_with(
            user_id=valid_user.id,
            first_name=None,
            last_name=None,
            email=None,
            username=None,
        )

    # CT-15.R11: usuário não encontrado retorna 404
    def test_patch_me_usuario_inexistente_retorna_404(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.update_profile.side_effect = UserNotFoundError(valid_user.id)

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.patch("/users/me", json={"first_name": "Joana"})

        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert valid_user.id in response.json()["detail"]

    # CT-15.R12 (CA-10 / integração real): atualização parcial via service + fakes
    def test_patch_me_integracao_real_parcial(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        fake_user_repo = FakeUserRepository()
        fake_access_level_repo = FakeAccessLevelRepository(
            levels=[
                AccessLevel(id=ADMIN_UUID, title="admin"),
                AccessLevel(id=USER_UUID, title="user"),
            ]
        )
        fake_user_repo.save(valid_user)
        service = UserService(
            user_repo=fake_user_repo,
            access_level_repo=fake_access_level_repo,
        )

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: service

        response = client.patch("/users/me", json={"first_name": "Joana"})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Joana"
        assert data["last_name"] == valid_user.last_name
        assert data["email"] == valid_user.email.value
        assert data["username"] == valid_user.username.value


class TestUserRouterChangePassword:
    """Testes do endpoint PUT /users/me/password (US-16)."""

    _PAYLOAD = {"current_password": "S3nh@Atual!", "new_password": "N0v@Senha!"}

    # CT-16.R01 (CA-01): dados válidos retornam 204 sem body
    def test_put_password_dados_validos_retorna_204(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.change_password.return_value = valid_user

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.put("/users/me/password", json=self._PAYLOAD)

        app.dependency_overrides.clear()

        assert response.status_code == 204
        assert response.text == ""
        user_service_mock.change_password.assert_called_once_with(
            user_id=valid_user.id,
            current_password=self._PAYLOAD["current_password"],
            new_password=self._PAYLOAD["new_password"],
        )

    # CT-16.R02 (CA-07): sem token retorna 401
    def test_put_password_sem_token_retorna_401(
        self,
        client: TestClient,
    ) -> None:
        response = client.put("/users/me/password", json=self._PAYLOAD)

        assert response.status_code == 401

    # CT-16.R03 (CA-03): senha atual incorreta retorna 401
    def test_put_password_senha_atual_incorreta_retorna_401(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.change_password.side_effect = InvalidCredentialsError()

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.put(
            "/users/me/password",
            json={"current_password": "errada", "new_password": "N0v@Senha!"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 401
        assert "Credenciais" in response.json()["detail"]

    # CT-16.R04 (CA-04): nova senha igual à atual retorna 400
    def test_put_password_nova_igual_atual_retorna_400(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.change_password.side_effect = SamePasswordError()

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.put(
            "/users/me/password",
            json={"current_password": "S3nh@Atual!", "new_password": "S3nh@Atual!"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400

    # CT-16.R05 (CA-05): nova senha fraca retorna 422
    def test_put_password_nova_fraca_retorna_422(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.change_password.side_effect = WeakPasswordError(
            "deve ter ao menos 8 caracteres"
        )

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.put(
            "/users/me/password",
            json={"current_password": "S3nh@Atual!", "new_password": "fraca"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 422
        assert "Senha fraca" in response.json()["detail"]

    # CT-16.R06: usuário não encontrado retorna 404
    def test_put_password_usuario_inexistente_retorna_404(
        self,
        app: FastAPI,
        client: TestClient,
        valid_user: User,
    ) -> None:
        user_service_mock = create_autospec(UserService, instance=True)
        user_service_mock.change_password.side_effect = UserNotFoundError(valid_user.id)

        app.dependency_overrides[get_current_user] = lambda: valid_user.id
        app.dependency_overrides[get_user_service] = lambda: user_service_mock

        response = client.put("/users/me/password", json=self._PAYLOAD)

        app.dependency_overrides.clear()

        assert response.status_code == 404
