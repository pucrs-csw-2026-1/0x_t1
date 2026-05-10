# app/adapters/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = "development"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    dynamodb_table_users: str = "user"

    dynamodb_table_access_levels: str = "access_level"

    seed_admin_email: str = "admin@local.dev"
    seed_admin_password: str = "Admin@123"


settings = Settings()  # type: ignore[call-arg]
