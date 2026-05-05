from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.adapters.api.dependencies import get_auth_service, get_current_user
from app.application.auth_service import AuthService
from app.domain.exceptions import (
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str

@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Credenciais invalidas."}},
    description=(
        "Autentica via OAuth2 Password Flow. "
        "O campo `username` recebe o email cadastrado."
    ),
)
def login(
    username: str = Form(..., description="Email cadastrado do usuario."),
    password: str = Form(..., description="Senha do usuario."),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        token_data = auth_service.login(email=username, password=password)
        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type="bearer",
        )
    except InvalidEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/refresh", response_model=RefreshTokenResponse, status_code=200)
def refresh(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RefreshTokenResponse:
    """Renova o access token usando um refresh token válido."""
    try:
        access_token = auth_service.refresh(request.refresh_token)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except TokenRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revogado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return RefreshTokenResponse(access_token=access_token)


@router.post("/logout", status_code=204)
def logout(
    body: LogoutRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """Revoga o refresh token do usuário autenticado.

    Requer autenticação via Bearer token (access token).
    """
    auth_service.logout(body.refresh_token)
    return None
