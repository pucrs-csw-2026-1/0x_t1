"""Router para endpoints administrativos (gate por scope 'admin')."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from pydantic import BaseModel, Field

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.adapters.api.user_router import UserResponse, to_user_response
from app.application.user_service import UserService
from app.domain.exceptions import (
    AccessLevelNotFoundError,
    InvalidPaginationError,
    UserNotFoundError,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class UserListResponse(BaseModel):
    items: list[UserResponse] = Field(..., description="Página atual de usuários.")
    next_cursor: str | None = Field(
        ...,
        description="Cursor para a próxima página. None indica fim da lista.",
        examples=["bd0babc3-bd93-443d-aefb-5193f5e1f08c"],
    )


class AdminUserUpdate(BaseModel):
    access_level: list[str] | None = Field(
        None,
        description=(
            "UUIDs do catálogo de access_level. Quando informado, "
            "substitui o conjunto atual do usuário."
        ),
        examples=[
            [
                "9e556479-7003-5916-9cd6-33f4227cec9b",
                "bace0701-15e3-5144-97c5-47487d543032",
            ]
        ],
    )
    is_active: bool | None = Field(
        None,
        description=(
            "Status de ativação. Quando informado, ativa (true) "
            "ou desativa (false) o usuário."
        ),
        examples=[False],
    )


@router.get(
    "/ping",
    status_code=200,
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Token sem permissão de admin."},
    },
    description="Endpoint de teste para verificar autenticação e autorização de admin.",
)
def admin_ping(
    user_id: Annotated[str, Security(get_current_user, scopes=["admin"])],
) -> dict[str, str]:
    """Endpoint de teste para verificar autenticação e autorização de admin."""
    return {"user_id": user_id, "status": "ok"}


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=200,
    responses={
        400: {"description": "Cursor inválido."},
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Permissão insuficiente."},
    },
    description="Lista usuários (somente admin).",
)
def admin_list_users(
    user_id: Annotated[str, Security(get_current_user, scopes=["admin"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> UserListResponse:
    try:
        page = user_service.list_users(limit=limit, cursor=cursor)
    except InvalidPaginationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserListResponse(
        items=[to_user_response(u) for u in page.items],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=200,
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Permissão insuficiente."},
        404: {"description": "Usuário não encontrado."},
    },
    description="Retorna os dados de um usuário pelo ID (somente admin).",
)
def admin_get_user(
    user_id: str,
    admin_id: Annotated[str, Security(get_current_user, scopes=["admin"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    try:
        user = user_service.get_user_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return to_user_response(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=200,
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Permissão insuficiente."},
        404: {"description": "Usuário não encontrado."},
        422: {"description": "UUID de access_level inválido."},
    },
    description="Atualiza access_level e/ou is_active de um usuário (somente admin).",
)
def admin_update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin_id: Annotated[str, Security(get_current_user, scopes=["admin"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    try:
        user = user_service.admin_update(
            admin_id=admin_id,
            target_user_id=user_id,
            access_level=payload.access_level,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except AccessLevelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return to_user_response(user)


@router.delete(
    "/users/{user_id}",
    status_code=204,
    responses={
        400: {"description": "Admin não pode desativar a si mesmo."},
        401: {"description": "Token ausente, inválido ou expirado."},
        403: {"description": "Permissão insuficiente."},
        404: {"description": "Usuário não encontrado."},
    },
    description="Desativa um usuário pelo ID (somente admin).",
)
def admin_delete_user(
    user_id: str,
    admin_id: Annotated[str, Security(get_current_user, scopes=["admin"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    if admin_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin não pode desativar a si mesmo.",
        )
    try:
        user_service.deactivate(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
