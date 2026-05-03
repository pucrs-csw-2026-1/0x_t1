from __future__ import annotations

from app.domain.exceptions import TokenRevokedError, UserNotFoundError
from app.ports.refresh_token_repository import RefreshTokenRepository
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository


class AuthService:
    """Use case de autenticação: refresh e logout (revogação de refresh token)."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_provider: TokenProvider,
        refresh_repo: RefreshTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_provider = token_provider
        self.refresh_repo = refresh_repo

    def logout(self, refresh_token: str) -> None:
        """Revoga o refresh token. Idempotente: não levanta erro se já estiver revogado."""
        # Marca como revogado (mesmo se já estiver revogado)
        self.refresh_repo.revoke(refresh_token)

    def refresh(self, refresh_token: str) -> str:
        """Gera um novo access token a partir de um refresh token.

        Levanta TokenRevokedError se o refresh token já tiver sido revogado.
        """
        # Verifica revogação primeiro
        if self.refresh_repo.is_revoked(refresh_token):
            raise TokenRevokedError()

        payload = self.token_provider.decode_token(refresh_token)
        user_id = payload.get("sub")
        if user_id is None:
            raise UserNotFoundError("")

        user = self.user_repo.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        # Gera um novo access token com os escopos do usuário
        return self.token_provider.generate_access_token(user_id, user.access_level)
