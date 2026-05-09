"""Auditoria de proteção de rotas (US-11).

Garante que toda rota registrada no app está protegida por get_current_user
(direta ou indiretamente via require_scope) OU está explicitamente declarada
como pública na allowlist abaixo.

Quando US futuras (15/16/17/14/18) adicionarem novas rotas, este teste
falha caso a auth seja esquecida — o desenvolvedor é forçado a tomar
uma decisão consciente: protege a rota ou adiciona à allowlist com
justificativa.

Nota: monta o app localmente em vez de importar app.main para evitar o
side-effect do load_dotenv() no top-level de main.py, que sobrescreve
AWS_ENDPOINT_URL e quebra a fixture mock_aws de outros testes.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.adapters.api.auth_router import router as auth_router
from app.adapters.api.dependencies import get_current_user
from app.adapters.api.user_router import router as user_router

PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("/health", "GET"),
    ("/users/register", "POST"),
    ("/users/me", "DELETE"),
    ("/auth/login", "POST"),
    ("/auth/refresh", "POST"),
}


def _build_app() -> FastAPI:
    """Monta o app espelhando app.main mas sem load_dotenv no top-level."""
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(user_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _depends_on_current_user(dep: Dependant) -> bool:
    """Verifica recursivamente se a chain de dependências chama get_current_user."""
    if dep.call is get_current_user:
        return True
    return any(_depends_on_current_user(sub) for sub in dep.dependencies)


def _api_routes(app: FastAPI) -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute)]


class TestRouteAuthAudit:
    def test_toda_rota_e_protegida_ou_publica_explicitamente(self) -> None:
        """CT-AUDIT-01: cada rota está em PUBLIC_ROUTES ou exige get_current_user."""
        app = _build_app()
        unprotected: list[tuple[str, str]] = []
        for route in _api_routes(app):
            for method in route.methods:
                key = (route.path, method)
                if key in PUBLIC_ROUTES:
                    continue
                if not _depends_on_current_user(route.dependant):
                    unprotected.append(key)

        assert not unprotected, (
            "Rotas sem proteção e sem entrada explícita em PUBLIC_ROUTES: "
            f"{unprotected}. Adicione Depends(get_current_user) ou inclua "
            "na allowlist com justificativa."
        )

    def test_allowlist_nao_contem_entradas_obsoletas(self) -> None:
        """CT-AUDIT-02: toda entrada da allowlist corresponde a uma rota real."""
        app = _build_app()
        registered: set[tuple[str, str]] = {
            (route.path, method)
            for route in _api_routes(app)
            for method in route.methods
        }
        obsoletas = PUBLIC_ROUTES - registered
        assert not obsoletas, (
            f"PUBLIC_ROUTES contém entradas que não existem mais no app: {obsoletas}"
        )
