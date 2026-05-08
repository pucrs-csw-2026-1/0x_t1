from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.application.user_service import UserService
from app.domain.exceptions import (
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidNameError,
    InvalidUsernameError,
    UserNotFoundError,
    WeakPasswordError,
)
from app.domain.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    username: str
    email: str
    access_level: list[str]
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    password: str
    access_level: list[str] | None = Field(
        default=None,
        deprecated=True,
        description="Ignorado. Cadastro público sempre cria perfil 'user'.",
    )


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username.value,
        email=user.email.value,
        access_level=user.access_level,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=200,
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        404: {"description": "Usuário não encontrado."},
    },
    description=(
        "Retorna os dados do usuário autenticado.\n\n"
        "Requer `Authorization: Bearer <access_token>` no header. "
        "Para testar via Swagger UI, clique em **Authorize** (cadeado) "
        "antes de executar."
    ),
)
def get_me(
    user_id: Annotated[str, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Retorna os dados do usuário autenticado."""
    try:
        user = user_service.get_user_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_user_response(user)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    responses={
        400: {"description": "Dados inválidos (email, senha, username ou nome)."},
        409: {"description": "Email já cadastrado."},
    },
)
def register_user(
    payload: UserCreate, user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """Cria uma nova conta de usuário."""
    try:
        user = user_service.register(
            first_name=payload.first_name,
            last_name=payload.last_name,
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (
        InvalidEmailError,
        WeakPasswordError,
        InvalidUsernameError,
        InvalidNameError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return to_user_response(user)
