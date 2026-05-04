from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.application.auth_service import AuthService
from app.domain.exceptions import InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


def get_auth_service() -> AuthService:
    """Dependency para resolver o AuthService na camada de API."""
    raise NotImplementedError("AuthService dependency not configured")


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        token_data = auth_service.login(
            email=form_data.username,
            password=form_data.password,
        )
        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type="bearer",
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
