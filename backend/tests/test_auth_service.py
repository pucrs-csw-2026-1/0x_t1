"""Testes unitários para AuthService (US-06 login, US-08 logout, US-13 scopes)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import create_autospec

import pytest
from jose import jwt

from app.adapters.config.settings import Settings
from app.adapters.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.domain.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)
from app.domain.user import User
from app.ports.password_hasher import PasswordHasher
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository
from tests.conftest import ADMIN_UUID, USER_UUID
from tests.fakes.access_level_repository import FakeAccessLevelRepository

SECRET = "chave-secreta-de-teste"
ALGORITHM = "HS256"
USER_ID = "usuario-123"
SCOPES = ["user:read", "user:write"]


@pytest.fixture
def user_repository_mock() -> UserRepository:
    return create_autospec(UserRepository, instance=True)


@pytest.fixture
def password_hasher_mock() -> PasswordHasher:
    return create_autospec(PasswordHasher, instance=True)


@pytest.fixture
def token_provider_mock() -> TokenProvider:
    return create_autospec(TokenProvider, instance=True)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key=SECRET,
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )  # type: ignore[call-arg]


@pytest.fixture
def jwt_token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


@pytest.fixture
def auth_service(
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
    token_provider_mock: TokenProvider,
    fake_access_level_repo: FakeAccessLevelRepository,
) -> AuthService:
    return AuthService(
        user_repository=user_repository_mock,
        password_hasher=password_hasher_mock,
        token_provider=token_provider_mock,
        access_level_repo=fake_access_level_repo,
    )


class TestAuthServiceLogin:
    """Testes do método login (US-06)."""

    def test_login_com_credenciais_validas_retorna_tokens(
        self,
        auth_service: AuthService,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-01: Login com email e senha válidos retorna tokens."""
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True
        token_provider_mock.generate_access_token.return_value = "access.jwt"
        token_provider_mock.generate_refresh_token.return_value = "refresh.jwt"

        result = auth_service.login(email=valid_user.email.value, password="Senha@123")

        assert result == {
            "access_token": "access.jwt",
            "refresh_token": "refresh.jwt",
            "token_type": "bearer",
        }
        password_hasher_mock.verify.assert_called_once()
        token_provider_mock.generate_access_token.assert_called_once()

    def test_login_com_email_inexistente_lanca_erro(
        self,
        auth_service: AuthService,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
    ) -> None:
        """CT-02: Email inexistente lança InvalidCredentialsError."""
        user_repository_mock.find_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            auth_service.login(email="naoexiste@example.com", password="Senha@123")

        password_hasher_mock.verify.assert_not_called()
        token_provider_mock.generate_access_token.assert_not_called()

    def test_login_com_senha_incorreta_lanca_erro(
        self,
        auth_service: AuthService,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-03: Senha incorreta lança InvalidCredentialsError."""
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = False

        with pytest.raises(InvalidCredentialsError):
            auth_service.login(email=valid_user.email.value, password="SenhaErrada@1")

        token_provider_mock.generate_access_token.assert_not_called()

    def test_login_com_email_malformado_lanca_credenciais_invalidas(
        self,
        auth_service: AuthService,
    ) -> None:
        """CT-04: email malformado vira InvalidCredentialsError (não vaza
        informação sobre formato/existência do usuário)."""
        with pytest.raises(InvalidCredentialsError):
            auth_service.login(email="email-invalido", password="Senha@123")


class TestAuthServiceLoginScopes:
    """Mapeamento UUID -> title nas scopes do JWT (US-13)."""

    def test_login_mapeia_uuids_de_access_level_para_titles(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        """CT-13.5-01: usuario com [USER_UUID, ADMIN_UUID] gera JWT com
        scopes=['user', 'admin'] (strings semanticas, nao UUIDs)."""
        valid_user.access_level = [USER_UUID, ADMIN_UUID]
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )

        tokens = auth_service.login(email=valid_user.email.value, password="Senha@123")

        access_payload = jwt_token_provider.decode_token(tokens["access_token"])
        refresh_payload = jwt_token_provider.decode_token(tokens["refresh_token"])
        assert access_payload["scopes"] == ["user", "admin"]
        assert refresh_payload["scopes"] == ["user", "admin"]

    def test_login_descarta_uuid_orfao_silenciosamente(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        """CT-13.5-02: UUID que nao existe no catalogo eh descartado;
        login nao quebra para o usuario por dessincronia do catalogo."""
        valid_user.access_level = [USER_UUID, "uuid-orfao-nao-existe"]
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )

        tokens = auth_service.login(email=valid_user.email.value, password="Senha@123")

        payload = jwt_token_provider.decode_token(tokens["access_token"])
        assert payload["scopes"] == ["user"]

    def test_login_com_access_level_vazio_emite_scopes_vazias(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        """CT-13.5-03: usuario sem perfis recebe JWT com scopes=[]; nao
        ganha permissoes implicitas."""
        valid_user.access_level = []
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )

        tokens = auth_service.login(email=valid_user.email.value, password="Senha@123")

        payload = jwt_token_provider.decode_token(tokens["access_token"])
        assert payload["scopes"] == []

    def test_login_nao_emite_uuids_brutos_nas_scopes(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
        valid_user: User,
    ) -> None:
        """CT-13.5-04: regressao explicita - JWT nao deve carregar UUIDs
        em scopes (Security(..., scopes=['admin']) compara strings exatas
        e UUIDs nunca casariam)."""
        valid_user.access_level = [ADMIN_UUID]
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )

        tokens = auth_service.login(email=valid_user.email.value, password="Senha@123")

        payload = jwt_token_provider.decode_token(tokens["access_token"])
        assert ADMIN_UUID not in payload["scopes"]
        assert "admin" in payload["scopes"]


class TestAuthServiceRefresh:
    """Testes do método refresh (US-06 + US-08)."""

    def test_refresh_token_valido_retorna_novo_access_token(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-04: Refresh token válido retorna novo access token."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)

        access_token = auth_service.refresh(refresh_token)

        payload = jwt_token_provider.decode_token(access_token)
        assert payload["sub"] == USER_ID

    def test_refresh_preserva_scopes_do_refresh_token(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-04b: refresh com refresh_token contendo scopes deve emitir
        access_token com os mesmos scopes (regressão: antes saía vazio
        porque generate_refresh_token não incluía scopes no payload)."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID, SCOPES)

        access_token = auth_service.refresh(refresh_token)

        payload = jwt_token_provider.decode_token(access_token)
        assert payload["scopes"] == SCOPES

    def test_login_seguido_de_refresh_preserva_scopes_do_usuario(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        valid_user: User,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-04c: ponta-a-ponta — login mapeia UUIDs do user.access_level
        para titles antes de emitir o refresh; o refresh subsequente preserva
        os titles no novo access_token. Ordem dos titles segue a ordem dos
        UUIDs no usuario."""
        valid_user.access_level = [USER_UUID, ADMIN_UUID]
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )

        tokens = auth_service.login(email=valid_user.email.value, password="Senha@123")
        new_access = auth_service.refresh(tokens["refresh_token"])

        payload = jwt_token_provider.decode_token(new_access)
        assert payload["scopes"] == ["user", "admin"]

    def test_refresh_token_expirado_lanca_excecao(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-05: Refresh token expirado lança TokenExpiredError."""
        from datetime import datetime, timedelta, timezone

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )
        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        refresh_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            auth_service.refresh(refresh_token)

    def test_refresh_token_invalido_lanca_excecao(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-06: Refresh token com assinatura inválida lança InvalidTokenError."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)
        parts = refresh_token.split(".")
        adulterado = parts[0] + "." + parts[1] + ".assinatura_invalida"

        with pytest.raises(InvalidTokenError):
            auth_service.refresh(adulterado)

    def test_refresh_token_com_revoked_flag_lanca_excecao(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-07: Refresh token com flag 'revoked=true' lança TokenRevokedError."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            access_level_repo=fake_access_level_repo,
        )
        revoked_payload: dict[str, Any] = {
            "sub": USER_ID,
            "revoked": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        refresh_token = jwt.encode(revoked_payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(TokenRevokedError):
            auth_service.refresh(refresh_token)


class TestAuthServiceLogout:
    """Testes do método logout (US-08)."""

    def test_logout_revoga_refresh_token(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-08: Logout revoga o refresh token no repositório."""
        refresh_repo = InMemoryRefreshTokenRepository()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            refresh_repository=refresh_repo,
            access_level_repo=fake_access_level_repo,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)

        # Token deve estar válido antes do logout
        assert not refresh_repo.is_revoked(refresh_token)

        auth_service.logout(refresh_token)

        # Após logout, o token deve estar revogado
        assert refresh_repo.is_revoked(refresh_token)

    def test_logout_idempotente(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-09: Logout é idempotente (sem erro ao revogar token já revogado)."""
        refresh_repo = InMemoryRefreshTokenRepository()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            refresh_repository=refresh_repo,
            access_level_repo=fake_access_level_repo,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)

        auth_service.logout(refresh_token)
        # Segunda chamada não deve lançar erro
        auth_service.logout(refresh_token)

        assert refresh_repo.is_revoked(refresh_token)

    def test_logout_sem_refresh_repository_nao_lanca_erro(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        fake_access_level_repo: FakeAccessLevelRepository,
    ) -> None:
        """CT-10: Logout sem RefreshRepository injetado não lança erro."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            refresh_repository=None,
            access_level_repo=fake_access_level_repo,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)

        # Não deve lançar erro mesmo sem repositório
        auth_service.logout(refresh_token)


class TestAuthServiceInactiveUser:
    """Testes para desativação de conta (US-17)."""

    def test_login_usuario_inativo_retorna_credenciais_invalidas(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-01: Login de usuário inativo retorna InvalidCredentialsError
        (não revela que a conta existe mas está inativa)."""
        # Marca o usuário como inativo
        valid_user.deactivate()

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=token_provider_mock,
        )
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True

        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(
                email=valid_user.email.value, password="SenhaCorreta@123"
            )

        # Não deve tentar gerar tokens
        token_provider_mock.generate_access_token.assert_not_called()
        token_provider_mock.generate_refresh_token.assert_not_called()
        # Exceção deve ser a mesma de credenciais inválidas (não específica)
        assert str(exc_info.value) == "Credenciais inválidas."

    def test_login_usuario_inativo_mesma_mensagem_usuario_inexistente(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-02: Login com usuário inativo retorna a mesma mensagem de erro
        que usuário inexistente (segurança: não enumera contas)."""
        valid_user.deactivate()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=token_provider_mock,
        )

        # Cenário 1: usuário inativo
        user_repository_mock.find_by_email.return_value = valid_user
        try:
            auth_service.login(
                email=valid_user.email.value, password="SenhaCorreta@123"
            )
        except InvalidCredentialsError as exc_inactive:
            msg_inactive = str(exc_inactive)

        # Cenário 2: usuário inexistente
        user_repository_mock.find_by_email.return_value = None
        try:
            auth_service.login(
                email="naoexiste@example.com", password="SenhaCorreta@123"
            )
        except InvalidCredentialsError as exc_notfound:
            msg_notfound = str(exc_notfound)

        # Ambos retornam a mesma mensagem
        assert msg_inactive == msg_notfound == "Credenciais inválidas."

    def test_login_senha_incorreta_usuario_inativo_retorna_credenciais_invalidas(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-03: Se usuário está inativo, rejeita antes de verificar senha
        (evita timing attacks, atua uniformemente)."""
        valid_user.deactivate()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=token_provider_mock,
        )
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = False  # Senha errada

        with pytest.raises(InvalidCredentialsError):
            auth_service.login(email=valid_user.email.value, password="SenhaErrada@123")

        # Verifica que não tentou validar a senha (rejeita antes)
        password_hasher_mock.verify.assert_not_called()

    def test_reativacao_permite_login(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-04: Após reativação, login com senha correta funciona novamente
        (transição ativo -> inativo -> ativo)."""
        # Desativa e depois reativa
        valid_user.deactivate()
        valid_user.activate()

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=token_provider_mock,
        )
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True
        token_provider_mock.generate_access_token.return_value = "access.jwt"
        token_provider_mock.generate_refresh_token.return_value = "refresh.jwt"

        result = auth_service.login(
            email=valid_user.email.value, password="SenhaCorreta@123"
        )

        assert result["access_token"] == "access.jwt"
        assert result["refresh_token"] == "refresh.jwt"
