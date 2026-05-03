from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.adapters.api.dependencies import get_current_user
from app.adapters.config.settings import settings
from app.adapters.dynamo_user_repository import DynamoUserRepository
from app.adapters.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService

router = APIRouter(prefix="/auth")


class LogoutRequest(BaseModel):
    refresh_token: str


def _get_auth_service() -> AuthService:
    repo = DynamoUserRepository(table_name=settings.dynamodb_table_users)
    token_provider = JwtTokenProvider(settings)
    refresh_repo = InMemoryRefreshTokenRepository()
    return AuthService(user_repo=repo, token_provider=token_provider, refresh_repo=refresh_repo)


@router.post("/logout", status_code=204)
def logout(
    body: LogoutRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(_get_auth_service)],
) -> None:
    """Revoga o refresh token do usuário autenticado.

    Requer autenticação via Bearer token (access token).
    """
    auth_service.logout(body.refresh_token)
    return None
