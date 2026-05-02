from abc import ABC, abstractmethod


class TokenProvider(ABC):
    """Port para emissao de tokens de autenticacao."""

    @abstractmethod
    def generate_access_token(self, user_id: str, scopes: list[str]) -> str:
        """Gera um access token contendo o identificador e os escopos do usuario."""
        ...

    @abstractmethod
    def generate_refresh_token(self, user_id: str) -> str:
        """Gera um refresh token para o usuario."""
        ...
