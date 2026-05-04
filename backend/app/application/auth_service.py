from app.domain.exceptions import InvalidCredentialsError, TokenRevokedError
from app.domain.user import Email
from app.ports.password_hasher import PasswordHasher
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository


class AuthService:
    """Caso de uso de autenticacao com email/senha."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_provider: TokenProvider,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_provider = token_provider

    def login(self, email: str, password: str) -> dict[str, str]:
        user = self._user_repository.find_by_email(Email(email))
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
        """Renova sessao a partir de um refresh token valido."""
        payload = self._token_provider.decode_token(refresh_token)

        if payload.get("revoked") is True:
            raise TokenRevokedError()

        user_id = payload["sub"]
        scopes = payload.get("scopes", [])
        return self._token_provider.generate_access_token(
            user_id=user_id,
            scopes=scopes,
        )
