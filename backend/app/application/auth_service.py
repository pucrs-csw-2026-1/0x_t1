from __future__ import annotations

from app.domain.exceptions import (
    InvalidCredentialsError,
    InvalidEmailError,
    TokenRevokedError,
)
from app.domain.user import Email
from app.ports.password_hasher import PasswordHasher
from app.ports.refresh_token_repository import RefreshTokenRepository
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository


class AuthService:
    """Use case de autenticação: login, refresh com revogação e logout."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_provider: TokenProvider,
        refresh_repository: RefreshTokenRepository | None = None,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_provider = token_provider
        self._refresh_repository = refresh_repository

    def login(self, email: str, password: str) -> dict[str, str]:
        """Autentica usuário com email e senha.

        Raises:
            InvalidCredentialsError: se email malformado, inexistente, ou senha
                incorreta. Email malformado é tratado como credencial inválida
                para não vazar informação sobre a base de usuários.
        """
        try:
            email_vo = Email(email)
        except InvalidEmailError as exc:
            raise InvalidCredentialsError() from exc

        user = self._user_repository.find_by_email(email_vo)
        if user is None:
            raise InvalidCredentialsError()

        if not self._password_hasher.verify(password, user.hashed_password.value):
            raise InvalidCredentialsError()

        access_token = self._token_provider.generate_access_token(
            user_id=user.id,
            scopes=list(user.access_level),
        )
        refresh_token = self._token_provider.generate_refresh_token(user_id=user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def refresh(self, refresh_token: str) -> str:
        """Renova o access token a partir de um refresh token válido.

        Verifica revogação antes de decodificar.

        Raises:
            TokenRevokedError: se o refresh token foi revogado.
        """
        # Verifica revogação primeiro (se repositório foi injetado)
        if self._refresh_repository is not None and self._refresh_repository.is_revoked(
            refresh_token
        ):
            raise TokenRevokedError()

        payload = self._token_provider.decode_token(refresh_token)

        # Fallback: verifica também o campo "revoked" no payload
        if payload.get("revoked") is True:
            raise TokenRevokedError()

        user_id = payload["sub"]
        scopes = payload.get("scopes", [])
        return self._token_provider.generate_access_token(
            user_id=user_id,
            scopes=scopes,
        )

    def logout(self, refresh_token: str) -> None:
        """Revoga o refresh token. Idempotente.

        Não levanta erro se já estiver revogado ou se repositório não foi injetado.
        """
        if self._refresh_repository is not None:
            self._refresh_repository.revoke(refresh_token)
