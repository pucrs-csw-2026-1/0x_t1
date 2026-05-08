"""Router para endpoints administrativos (gate por scope 'admin')."""

from typing import Annotated

from fastapi import APIRouter, Security

from app.adapters.api.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


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
