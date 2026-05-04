from collections.abc import Callable

from fastapi import HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from app.adapters.config.settings import settings
from app.adapters.dynamo_user_repository import DynamoUserRepository
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.application.user_service import UserService
from app.domain.exceptions import InvalidTokenError, TokenExpiredError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_current_user(
    security_scopes: SecurityScopes,
    token: str | None = Security(oauth2_scheme),
) -> str:
    """Valida o Bearer token e verifica os escopos requeridos.

    Raises:
        HTTPException 401: token ausente, inválido ou expirado.
        HTTPException 403: token válido mas sem o escopo requerido.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_provider = JwtTokenProvider(settings)
    try:
        payload = token_provider.decode_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if security_scopes.scopes:
        token_scopes: list[str] = payload.get("scopes", [])
        for scope in security_scopes.scopes:
            if scope not in token_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permissão insuficiente: requer '{scope}'.",
                )

    user_id: str = payload["sub"]
    return user_id


def require_scope(required_scope: str) -> Callable[..., str]:
    """Retorna uma dependência FastAPI que exige o escopo informado."""

    def _dependency(
        user_id: str = Security(get_current_user, scopes=[required_scope]),
    ) -> str:
        return user_id

    return _dependency


def get_user_service() -> UserService:
    """Constrói e retorna uma instância de UserService."""
    repo = DynamoUserRepository(table_name=settings.dynamodb_table_users)
    return UserService(user_repo=repo)


def get_auth_service() -> AuthService:
    """Constrói e retorna uma instância de AuthService."""
    from app.adapters.bcrypt_password_hasher import BcryptPasswordHasher
    from app.adapters.in_memory_refresh_token_repository import (
        InMemoryRefreshTokenRepository,
    )

    user_repository = DynamoUserRepository(table_name=settings.dynamodb_table_users)
    password_hasher = BcryptPasswordHasher()
    token_provider = JwtTokenProvider(settings)
    refresh_repository = InMemoryRefreshTokenRepository()

    return AuthService(
        user_repository=user_repository,
        password_hasher=password_hasher,
        token_provider=token_provider,
        refresh_repository=refresh_repository,
    )
