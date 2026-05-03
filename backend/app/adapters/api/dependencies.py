from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.adapters.config.settings import settings
from app.adapters.dynamo_user_repository import DynamoUserRepository
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.user_service import UserService
from app.domain.exceptions import InvalidTokenError, TokenExpiredError

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = _bearer,  # type: ignore[assignment]
) -> str:
    """Valida o Bearer token e retorna o user_id (claim sub).

    Raises:
        HTTPException 401: token ausente, inválido ou expirado.
    """
    token_provider = JwtTokenProvider(settings)
    try:
        payload = token_provider.decode_token(credentials.credentials)
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload["sub"]
    return user_id


def get_user_service() -> UserService:
    """Constrói e retorna uma instância de UserService."""
    repo = DynamoUserRepository(table_name=settings.dynamodb_table_users)
    return UserService(user_repo=repo)
