"""Testes unitários para validação de escopos via require_scope (US-12)
e cobertura de decisão do get_current_user (US-11)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import SecurityScopes
from jose import jwt

from app.adapters.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_user_service,
)
from app.adapters.config.settings import Settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.application.user_service import UserService

SECRET = "chave-secreta-de-teste"
ALGORITHM = "HS256"
USER_ID = "usuario-123"


@pytest.fixture
def token_provider() -> JwtTokenProvider:
    s = Settings(  # type: ignore[call-arg]
        secret_key=SECRET,
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )
    return JwtTokenProvider(s)


def _call(
    token_provider: JwtTokenProvider,
    token: str | None,
    required_scopes: list[str],
) -> str:
    """Chama get_current_user injetando o token_provider de teste."""
    with patch(
        "app.adapters.api.dependencies.JwtTokenProvider",
        return_value=token_provider,
    ):
        return get_current_user(
            security_scopes=SecurityScopes(scopes=required_scopes),
            token=token,
        )


class TestRequireScope:
    # CT-01 (partição — autorizado): usuário com role admin acessa rota restrita a admin
    def test_usuario_com_scope_admin_e_autorizado(
        self, token_provider: JwtTokenProvider
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["admin"])

        user_id = _call(token_provider, token, required_scopes=["admin"])

        assert user_id == USER_ID

    # CT-02 (partição — não autorizado): usuário com role user é rejeitado em rota admin
    def test_usuario_com_scope_user_e_rejeitado_em_rota_admin(
        self, token_provider: JwtTokenProvider
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["user"])

        with pytest.raises(HTTPException) as exc_info:
            _call(token_provider, token, required_scopes=["admin"])

        assert exc_info.value.status_code == 403

    # CT-03 (partição — sem roles): usuário sem scopes é rejeitado em rota restrita
    def test_usuario_sem_scopes_e_rejeitado(
        self, token_provider: JwtTokenProvider
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=[])

        with pytest.raises(HTTPException) as exc_info:
            _call(token_provider, token, required_scopes=["admin"])

        assert exc_info.value.status_code == 403

    # CT-04: token contém campo scopes com as roles do usuário
    def test_token_contem_claim_scopes(self, token_provider: JwtTokenProvider) -> None:
        roles = ["admin", "user:read"]
        token = token_provider.generate_access_token(USER_ID, scopes=roles)

        payload = token_provider.decode_token(token)

        assert payload["scopes"] == roles

    # CT-05: token ausente retorna 401
    def test_token_ausente_retorna_401(self, token_provider: JwtTokenProvider) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _call(token_provider, token=None, required_scopes=["admin"])

        assert exc_info.value.status_code == 401

    # CT-06: token inválido retorna 401
    def test_token_invalido_retorna_401(self, token_provider: JwtTokenProvider) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _call(token_provider, token="token.invalido.assinado", required_scopes=[])

        assert exc_info.value.status_code == 401

    # CT-07: rota sem escopo requerido aceita qualquer token válido
    def test_rota_sem_scope_aceita_token_valido(
        self, token_provider: JwtTokenProvider
    ) -> None:
        token = token_provider.generate_access_token(USER_ID, scopes=["user"])

        user_id = _call(token_provider, token, required_scopes=[])

        assert user_id == USER_ID

    # CT-11: token expirado retorna 401 (cobertura de decisão US-11)
    def test_token_expirado_retorna_401(self, token_provider: JwtTokenProvider) -> None:
        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "scopes": ["user"],
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            _call(token_provider, expired_token, required_scopes=[])

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token expirado."


class TestGetUserService:
    """Testes para get_user_service()."""

    def test_get_user_service_retorna_instancia(self) -> None:
        """CT-08: get_user_service retorna uma instância de UserService."""
        service = get_user_service()

        assert isinstance(service, UserService)


class TestGetAuthService:
    """Testes para get_auth_service()."""

    def test_get_auth_service_retorna_instancia(self) -> None:
        """CT-09: get_auth_service retorna uma instância de AuthService."""
        service = get_auth_service()

        assert isinstance(service, AuthService)
