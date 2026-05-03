from app.domain.exceptions import TokenRevokedError
from app.ports.token_provider import TokenProvider


class AuthService:
    def __init__(self, token_provider: TokenProvider) -> None:
        self._token_provider = token_provider

    def refresh(self, refresh_token: str) -> str:
        """Renova sessão a partir de um refresh token válido.

        Raises:
            InvalidTokenError: token inválido/malformado.
            TokenExpiredError: token expirado.
            TokenRevokedError: token marcado como revogado.
        """
        payload = self._token_provider.decode_token(refresh_token)

        if payload.get("revoked") is True:
            raise TokenRevokedError()

        user_id = payload["sub"]
        scopes = payload.get("scopes", [])
        return self._token_provider.generate_access_token(user_id, scopes)
