from datetime import datetime, timedelta, timezone
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt

from app.adapters.config.settings import Settings
from app.domain.exceptions import InvalidTokenError, TokenExpiredError
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository


class JwtTokenProvider(TokenProvider):
    def __init__(
        self, settings: Settings, user_repository: UserRepository | None = None
    ) -> None:
        self._settings = settings
        self._user_repository = user_repository

    def generate_access_token(self, user_id: str, scopes: list[str]) -> str:
        """Gera um JWT de acesso com claims sub, scopes e exp."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        payload: dict[str, Any] = {
            "sub": user_id,
            "scopes": scopes,
            "exp": expire,
        }
        # Optionally include user email in the token if a user repository is available
        try:
            if self._user_repository is not None:
                user = self._user_repository.find_by_id(user_id)
                if user is not None:
                    payload["email"] = user.email.value
        except Exception:
            # Be defensive: do not break token generation if repository lookup fails
            pass
        token: str = jwt.encode(
            payload, self._settings.secret_key, algorithm=self._settings.algorithm
        )
        return token

    def generate_refresh_token(
        self, user_id: str, scopes: list[str] | None = None
    ) -> str:
        """Gera um JWT de refresh com claims sub, scopes e exp."""
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        payload: dict[str, Any] = {
            "sub": user_id,
            "scopes": scopes or [],
            "exp": expire,
        }
        token: str = jwt.encode(
            payload, self._settings.secret_key, algorithm=self._settings.algorithm
        )
        return token

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decodifica e valida o JWT, retornando o payload.

        Raises:
            TokenExpiredError: se o token estiver expirado.
            InvalidTokenError: se assinatura inválida, chave incorreta ou sem claim sub.
        """
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._settings.secret_key,
                algorithms=[self._settings.algorithm],
            )
        except ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError:
            raise InvalidTokenError()

        if "sub" not in payload:
            raise InvalidTokenError()

        return payload
