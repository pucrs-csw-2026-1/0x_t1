"""Router para endpoints administrativos (gate por scope 'admin')."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from pydantic import BaseModel

from app.adapters.api.dependencies import get_current_user, get_user_service
from app.adapters.api.user_router import UserResponse, to_user_response
from app.application.user_service import UserService
from app.domain.exceptions import InvalidPaginationError

router = APIRouter(prefix="/admin", tags=["admin"])


class UserListResponse(BaseModel):
    items: list[UserResponse]
    next_cursor: str | None


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
