from datetime import datetime, timedelta, timezone
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt

from app.adapters.config.settings import Settings, read_key
from app.domain.exceptions import InvalidTokenError, TokenExpiredError
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository


class JwtTokenProvider(TokenProvider):
    """Emite e valida JWTs assinados em RS256 (US-28).

    Assina com a chave privada e valida com a pública (assimétrico): os demais
    microserviços validam o token apenas com a chave pública publicada no
    JWKS, sem compartilhar segredo. Todo token carrega `principal_type`
    distinguindo pessoa (`user`) de máquina (`service`, em iteração futura).
    """

    def __init__(
        self, settings: Settings, user_repository: UserRepository | None = None
    ) -> None:
        self._settings = settings
        self._user_repository = user_repository
        self._private_key = read_key(settings.rsa_private_key_path)
        self._public_key = read_key(settings.rsa_public_key_path)
        self._headers = {"kid": settings.jwt_kid}

    def generate_access_token(self, user_id: str, scopes: list[str]) -> str:
        """Gera um JWT de acesso com claims sub, scopes, principal_type, type e exp."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        payload: dict[str, Any] = {
            "sub": user_id,
            "scopes": scopes,
            "principal_type": "user",
            "type": "access",
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
            payload,
            self._private_key,
            algorithm=self._settings.algorithm,
            headers=self._headers,
        )
        return token

    def generate_refresh_token(
        self, user_id: str, scopes: list[str] | None = None
    ) -> str:
        """Gera um JWT de refresh com claims sub, scopes, principal_type, type e exp."""
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        payload: dict[str, Any] = {
            "sub": user_id,
            "scopes": scopes or [],
            "principal_type": "user",
            "type": "refresh",
            "exp": expire,
        }
        token: str = jwt.encode(
            payload,
            self._private_key,
            algorithm=self._settings.algorithm,
            headers=self._headers,
        )
        return token

    def generate_service_token(self, client_id: str, scopes: list[str]) -> str:
        """Gera um access token de máquina (client_credentials).

        Carrega `principal_type=service` e `sub=client_id` — distingue
        identidade de máquina de identidade de pessoa. Sem refresh token
        (padrão OAuth2 para client_credentials). Marca `type=access` por ser
        um token de acesso (de máquina).
        """
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        payload: dict[str, Any] = {
            "sub": client_id,
            "scopes": scopes,
            "principal_type": "service",
            "type": "access",
            "exp": expire,
        }
        token: str = jwt.encode(
            payload,
            self._private_key,
            algorithm=self._settings.algorithm,
            headers=self._headers,
        )
        return token

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decodifica e valida o JWT (assinatura RS256), retornando o payload.

        Raises:
            TokenExpiredError: se o token estiver expirado.
            InvalidTokenError: se assinatura inválida, chave incorreta ou sem claim sub.
        """
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._public_key,
                algorithms=[self._settings.algorithm],
            )
        except ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError:
            raise InvalidTokenError()

        if "sub" not in payload:
            raise InvalidTokenError()

        return payload
