"""Endpoints `.well-known` — publicação da chave pública via JWKS (US-28).

Permite que outros microserviços (ex.: Metrics) validem os JWTs emitidos por
este serviço usando apenas a chave pública, sem compartilhar segredo.
"""

from typing import Any

from fastapi import APIRouter
from jose import jwk

from app.adapters.config.settings import read_key, settings

router = APIRouter(tags=["well-known"])


@router.get(
    "/.well-known/jwks.json",
    status_code=200,
    description=(
        "Conjunto de chaves públicas (JWKS) para validação dos JWTs RS256. "
        "Os consumidores casam o `kid` do header do token com a chave aqui."
    ),
)
def jwks() -> dict[str, list[dict[str, Any]]]:
    """Retorna a chave pública RS256 em formato JWKS."""
    public_pem = read_key(settings.rsa_public_key_path)
    key_dict = jwk.construct(public_pem, algorithm=settings.algorithm).to_dict()
    # Normaliza para JSON (jose pode devolver bytes em n/e) e anexa metadados.
    jwk_entry: dict[str, Any] = {
        k: (v.decode() if isinstance(v, bytes) else v) for k, v in key_dict.items()
    }
    jwk_entry.update(
        {
            "use": "sig",
            "alg": settings.algorithm,
            "kid": settings.jwt_kid,
        }
    )
    return {"keys": [jwk_entry]}
