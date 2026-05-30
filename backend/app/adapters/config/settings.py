# app/adapters/config/settings.py
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = "development"
    # secret_key permanece para compatibilidade de configuração, mas NÃO é mais
    # usado: a assinatura dos JWTs migrou de HS256 (segredo compartilhado) para
    # RS256 (par de chaves) na US-28.
    secret_key: str | None = None
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # RS256 (US-28): caminhos para o par de chaves. Em dev/CI aponta para o
    # par versionado em backend/keys/ (dev-only). Em produção, sobrescreva via
    # env apontando para chaves montadas de um cofre de segredos (ver US-23).
    rsa_private_key_path: str = "keys/dev_private.pem"
    rsa_public_key_path: str = "keys/dev_public.pem"
    # Identificador da chave publicado no header dos tokens e no JWKS; os
    # consumidores casam o `kid` do token com a chave do JWKS.
    jwt_kid: str = "auth-dev-key"

    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    dynamodb_table_users: str = "user"

    seed_admin_email: str = "admin@local.dev"
    seed_admin_password: str = "Admin@123"


@lru_cache(maxsize=8)
def read_key(path: str) -> str:
    """Lê e cacheia o conteúdo PEM de uma chave a partir do caminho.

    Cacheado por caminho para evitar I/O de disco a cada token (o
    get_current_user instancia o provider por request).
    """
    return Path(path).read_text(encoding="utf-8")


settings = Settings()
