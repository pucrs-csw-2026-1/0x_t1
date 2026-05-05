from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.application.user_service import UserService
from app.domain.user import User

router = APIRouter(prefix="/users")


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
    access_level: list[str] | None = None


def _to_response(user: User) -> UserResponse:
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
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def get_me(
    user_id: Annotated[str, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Retorna os dados do usuário autenticado."""
    user = user_service.get_user_by_id(user_id)
    return _to_response(user)


@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(
    payload: UserCreate, user_service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """Cria uma nova conta de usuário."""
    user = user_service.register(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        access_level=payload.access_level,
    )
    return _to_response(user)
