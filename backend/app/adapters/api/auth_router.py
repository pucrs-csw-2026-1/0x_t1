from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.api.dependencies import get_auth_service, get_current_user
from app.application.auth_service import AuthService
from app.domain.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="JWT de acesso. Tempo de vida curto (default 30min).",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZDBiYWJjMy1iZDkzLTQ0M2QtYWVmYi01MTkzZjVlMWYwOGMiLCJzY29wZXMiOlsidXNlciJdLCJleHAiOjE3NjI4NDc2MDB9.fake-signature"
        ],
    )
    refresh_token: str = Field(
        ...,
        description="Token de renovação. Tempo de vida longo (default 7 dias).",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZDBiYWJjMy1iZDkzLTQ0M2QtYWVmYi01MTkzZjVlMWYwOGMiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2MzQ1MjQwMH0.fake-signature"
        ],
    )
    token_type: Literal["bearer"] = Field(
        "bearer", description="Tipo do token. Sempre 'bearer'."
    )


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="Refresh token recebido no login.",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZDBiYWJjMy1iZDkzLTQ0M2QtYWVmYi01MTkzZjVlMWYwOGMiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2MzQ1MjQwMH0.fake-signature"
        ],
    )


class RefreshTokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="Novo JWT de acesso. Mesmo formato do login.",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZDBiYWJjMy1iZDkzLTQ0M2QtYWVmYi01MTkzZjVlMWYwOGMiLCJzY29wZXMiOlsidXNlciJdLCJleHAiOjE3NjI4NDc2MDB9.fake-signature"
        ],
    )
    token_type: Literal["bearer"] = Field(
        "bearer", description="Tipo do token. Sempre 'bearer'."
    )


class LogoutRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="Refresh token a ser revogado.",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiZDBiYWJjMy1iZDkzLTQ0M2QtYWVmYi01MTkzZjVlMWYwOGMiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2MzQ1MjQwMH0.fake-signature"
        ],
    )


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
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=200,
    description=(
        "Renova o access token a partir de um refresh token válido. "
        "**Não requer Authorization header** — o refresh token vai no body. "
        "Retorna apenas o novo access token; o refresh token original "
        "permanece válido até expirar ou ser revogado via /auth/logout."
    ),
)
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

    return RefreshTokenResponse(access_token=access_token, token_type="bearer")


@router.post(
    "/logout",
    status_code=204,
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
    description=(
        "Revoga o refresh token do usuário autenticado.\n\n"
        "**Requer dois tokens em paralelo:**\n"
        "- `Authorization: Bearer <access_token>` no header (validação da sessão);\n"
        '- `{"refresh_token": "<refresh_token>"}` no body (alvo da revogação).\n\n'
        "Para testar via Swagger UI: clique no botão **Authorize** "
        "(cadeado, canto superior direito), preencha email/senha e autorize. "
        "O Swagger passa a injetar o Authorization header automaticamente "
        "neste e nos demais endpoints protegidos."
    ),
)
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
