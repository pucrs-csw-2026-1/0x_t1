from abc import ABC, abstractmethod
from typing import Any


class TokenProvider(ABC):
    """Port para geração e decodificação de tokens de autenticação."""

    @abstractmethod
    def generate_access_token(self, user_id: str, scopes: list[str]) -> str:
        """Gera um access token para o usuário com os escopos fornecidos."""
        ...

    @abstractmethod
    def generate_refresh_token(
        self, user_id: str, scopes: list[str] | None = None
    ) -> str:
        """Gera um refresh token para o usuário.

        ``scopes`` é incluído no payload para que ``refresh`` possa emitir
        novo access token preservando os escopos originais (sem precisar
        bater no banco).
        """
        ...

    @abstractmethod
    def decode_token(self, token: str) -> dict[str, Any]:
        """Decodifica e valida o token, retornando seu payload.

        Raises:
            InvalidTokenError: se o token for inválido ou malformado.
            TokenExpiredError: se o token estiver expirado.
        """
        ...
