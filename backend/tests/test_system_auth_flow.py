"""Testes de sistema do fluxo completo de autenticação.

Diferente dos testes em ``test_auth_router.py`` / ``test_user_router.py``,
estes NÃO mockam o AuthService nem o UserService — exercem o pipeline real
do FastAPI passando por:

    auth_router/user_router → dependencies (DI) → AuthService/UserService
        → DynamoUserRepository (boto3) → DynamoDB (mockado por moto)

Cobrem o golden path encadeado e os principais ramos de erro. Esta camada
é a que pega bugs como o do singleton de refresh tokens (se voltar) e o
de scopes ausentes pós-refresh — coisas invisíveis quando o service é
mockado nos testes de unidade do router.
"""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws

from app.adapters.api import dependencies as deps_module
from app.adapters.api.auth_router import router as auth_router
from app.adapters.api.user_router import router as user_router
from tests.conftest import ADMIN_UUID, USER_UUID

VALID_PAYLOAD = {
    "first_name": "Maria",
    "last_name": "Silva",
    "username": "maria.silva",
    "email": "maria@example.com",
    "password": "Senha@123",
}


def _create_tables() -> None:
    """Cria 'user' e 'access_level' (seedada) no DynamoDB mockado, espelhando
    o schema/seed do Terraform."""
    ddb = boto3.resource("dynamodb", region_name="us-east-1")

    ddb.create_table(
        TableName="user",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "username-index",
                "KeySchema": [{"AttributeName": "username", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    access_table = ddb.create_table(
        TableName="access_level",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    access_table.put_item(Item={"id": ADMIN_UUID, "title": "admin"})
    access_table.put_item(Item={"id": USER_UUID, "title": "user"})


@pytest.fixture
def system_app() -> Iterator[FastAPI]:
    """App real + DDB mockado + reset do singleton de refresh tokens.

    O reset é crítico: o ``_refresh_token_repository`` em
    ``dependencies.py`` é singleton de processo (ver fix do logout no
    PR #57). Sem o reset, um teste contamina o seguinte.
    """
    with mock_aws():
        _create_tables()
        deps_module._refresh_token_repository._revoked.clear()

        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(user_router)
        yield app


@pytest.fixture
def client(system_app: FastAPI) -> TestClient:
    return TestClient(system_app)


def _register(client: TestClient, **overrides: object) -> dict[str, object]:
    payload = {**VALID_PAYLOAD, **overrides}
    response = client.post("/users/register", json=payload)
    return {"status": response.status_code, "body": response.json()}


def _login(
    client: TestClient,
    email: str = VALID_PAYLOAD["email"],
    password: str = VALID_PAYLOAD["password"],
) -> dict[str, object]:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    return {"status": response.status_code, "body": response.json()}


class TestHappyPath:
    """Fluxo ponta-a-ponta esperado em produção."""

    def test_register_login_me_refresh_logout_e_refresh_revogado(
        self, client: TestClient
    ) -> None:
        """CT-SYS-01: golden path completo — todas as etapas devem retornar
        os status esperados E o refresh deve ser rejeitado após logout
        (regressão do bug do singleton de refresh tokens)."""
        # 1. Register → 201
        r_register = _register(client)
        assert r_register["status"] == 201
        body = r_register["body"]
        assert isinstance(body, dict)
        assert body["email"] == VALID_PAYLOAD["email"]
        user_id = body["id"]

        # 2. Login → 200 com access + refresh
        r_login = _login(client)
        assert r_login["status"] == 200
        login_body = r_login["body"]
        assert isinstance(login_body, dict)
        access_token = login_body["access_token"]
        refresh_token = login_body["refresh_token"]
        assert access_token and refresh_token

        # 3. /users/me com Bearer access → 200 com dados do user
        r_me = client.get(
            "/users/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert r_me.status_code == 200
        assert r_me.json()["id"] == user_id

        # 4. /auth/refresh → 200 com novo access (refresh original ainda
        #    válido, design não-rotativo)
        r_refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert r_refresh.status_code == 200
        new_access = r_refresh.json()["access_token"]
        # Pode ou não diferir do original (depende se o segundo do exp
        # avançou); o que importa é que veio um JWT decodificável.
        assert new_access
        assert "refresh_token" not in r_refresh.json()  # design não-rotativo

        # 5. /auth/logout exige Bearer (access) E refresh no body → 204
        r_logout = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        assert r_logout.status_code == 204

        # 6. /auth/refresh com o mesmo refresh → 401 (revogado).
        #    Sem o singleton de refresh repo, este passo passaria — é o
        #    teste que pega o regression do bug do logout.
        r_refresh_after = client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert r_refresh_after.status_code == 401
        assert "revogado" in r_refresh_after.json()["detail"].lower()


class TestRegisterErrors:
    """POST /users/register — mapeamento de erros de domínio."""

    def test_email_duplicado_retorna_409(self, client: TestClient) -> None:
        """CT-SYS-02: segundo register com mesmo email → 409."""
        first = _register(client)
        assert first["status"] == 201

        second = _register(client)
        assert second["status"] == 409
        body = second["body"]
        assert isinstance(body, dict)
        assert VALID_PAYLOAD["email"] in body["detail"]

    def test_email_malformado_retorna_400(self, client: TestClient) -> None:
        """CT-SYS-03: email sem @ vira 400 (não 500)."""
        result = _register(client, email="nao-eh-email")
        assert result["status"] == 400
        body = result["body"]
        assert isinstance(body, dict)
        assert "email" in body["detail"].lower()

    def test_senha_fraca_retorna_400(self, client: TestClient) -> None:
        """CT-SYS-04: senha sem complexidade vira 400 (não 500)."""
        result = _register(client, password="abc", email="other@example.com")
        assert result["status"] == 400
        body = result["body"]
        assert isinstance(body, dict)
        assert "senha" in body["detail"].lower()

    def test_username_invalido_retorna_400(self, client: TestClient) -> None:
        """CT-SYS-05: username < 8 chars vira 400 (não 500)."""
        result = _register(client, username="abc", email="other@example.com")
        assert result["status"] == 400


class TestLoginErrors:
    """POST /auth/login — todos os ramos de erro retornam 401 unificado."""

    def test_email_inexistente_retorna_401(self, client: TestClient) -> None:
        """CT-SYS-06: email não cadastrado → 401."""
        result = _login(client, email="ninguem@example.com")
        assert result["status"] == 401
        body = result["body"]
        assert isinstance(body, dict)
        assert body["detail"] == "Credenciais inválidas."

    def test_senha_errada_retorna_401(self, client: TestClient) -> None:
        """CT-SYS-07: senha incorreta → 401."""
        _register(client)
        result = _login(client, password="SenhaErrada@9")
        assert result["status"] == 401
        body = result["body"]
        assert isinstance(body, dict)
        assert body["detail"] == "Credenciais inválidas."

    def test_email_malformado_retorna_401_credenciais_invalidas(
        self, client: TestClient
    ) -> None:
        """CT-SYS-08: email malformado vira 401 'Credenciais inválidas'
        (não 400 vazando o formato — regressão do PR #55)."""
        result = _login(client, email="nao-eh-email")
        assert result["status"] == 401
        body = result["body"]
        assert isinstance(body, dict)
        assert body["detail"] == "Credenciais inválidas."


class TestProtectedEndpointsAuth:
    """Endpoints protegidos: /users/me e /auth/logout."""

    def test_me_sem_authorization_retorna_401(self, client: TestClient) -> None:
        """CT-SYS-09: GET /users/me sem header → 401 'Token ausente'."""
        response = client.get("/users/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Token ausente."

    def test_me_token_malformado_retorna_401(self, client: TestClient) -> None:
        """CT-SYS-10: GET /users/me com Bearer não-JWT → 401."""
        response = client.get(
            "/users/me", headers={"Authorization": "Bearer nao.eh.um.jwt"}
        )
        assert response.status_code == 401

    def test_logout_sem_authorization_retorna_401(self, client: TestClient) -> None:
        """CT-SYS-11: POST /auth/logout sem header → 401, não chega no body.
        (Esse é o cenário que confundia no Swagger UI — endpoint exige
        access_token no header E refresh_token no body simultaneamente.)"""
        response = client.post("/auth/logout", json={"refresh_token": "qualquer.coisa"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Token ausente."

    def test_refresh_preserva_scopes_apos_login(self, client: TestClient) -> None:
        """CT-SYS-12: scopes do user devem sobreviver ao /auth/refresh
        (regressão direta do PR #58 — antes saíam vazios). Com a US-13
        a promoção é feita direto no banco, já que o register público
        ignora access_level do payload (segurança contra auto-promoção)."""
        register_resp = _register(client)
        assert register_resp["status"] == 201
        body = register_resp["body"]
        assert isinstance(body, dict)
        user_id = body["id"]

        # Promove o usuário no banco para [user, admin] — simula uma
        # operação administrativa (US-18 cobrirá esse fluxo).
        boto3.resource("dynamodb", region_name="us-east-1").Table("user").update_item(
            Key={"id": user_id},
            UpdateExpression="SET access_level = :a",
            ExpressionAttributeValues={":a": [USER_UUID, ADMIN_UUID]},
        )

        login = _login(client)
        assert login["status"] == 200
        login_body = login["body"]
        assert isinstance(login_body, dict)

        r_refresh = client.post(
            "/auth/refresh", json={"refresh_token": login_body["refresh_token"]}
        )
        assert r_refresh.status_code == 200

        # Decodifica o novo access_token sem verificar assinatura — o
        # objetivo aqui é só ler o claim 'scopes' do payload.
        from jose import jwt

        new_access = r_refresh.json()["access_token"]
        payload = jwt.get_unverified_claims(new_access)
        assert sorted(payload["scopes"]) == ["admin", "user"]
