import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Carrega .env em os.environ antes do boto3 instanciar clientes,
# para que AWS_ENDPOINT_URL/credenciais apontem ao Ministack em dev.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.adapters.api.admin_router import router as admin_router  # noqa: E402
from app.adapters.api.auth_router import router as auth_router  # noqa: E402
from app.adapters.api.user_router import router as user_router  # noqa: E402
from app.adapters.api.well_known_router import (  # noqa: E402
    router as well_known_router,
)
from app.adapters.config.settings import settings  # noqa: E402
from app.adapters.dynamo_user_repository import DynamoUserRepository  # noqa: E402
from app.application.user_service import UserService  # noqa: E402
from app.domain.access_level import Role  # noqa: E402
from app.domain.user import Email  # noqa: E402
from app.ports.user_repository import UserRepository  # noqa: E402

logger = logging.getLogger(__name__)


def _seed_root_admin(user_repo: UserRepository) -> None:
    if user_repo.find_by_email(Email(settings.seed_admin_email)) is not None:
        return  # idempotente — já existe

    service = UserService(user_repo=user_repo)
    user = service.register(
        first_name="Admin",
        last_name="Root",
        username="admin.root",
        email=settings.seed_admin_email,
        password=settings.seed_admin_password,
    )

    user.change_role(Role.ADMIN)
    user_repo.save(user)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Bootstrap defensivo apenas em ambiente de desenvolvimento.

    Em ``app_env=development`` garante que a tabela do DynamoDB existe
    quando o app sobe — útil quando a Ministack foi recriada e nem
    sempre o desenvolvedor lembra de rodar ``terraform apply``.

    Em produção ``app_env`` deve ser diferente de ``development`` para
    que o app NÃO crie infra em runtime: isso é responsabilidade do
    pipeline de IaC. Falhas no bootstrap são logadas mas não quebram
    o startup — o erro real continua aparecendo no primeiro request.
    """
    if settings.app_env == "development":
        try:
            DynamoUserRepository(
                table_name=settings.dynamodb_table_users,
                auto_create=True,
            )
            logger.info(
                "[lifespan] tabela '%s' garantida em %s",
                settings.dynamodb_table_users,
                settings.aws_endpoint_url or "AWS",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[lifespan] falhou ao garantir tabela '%s': %s",
                settings.dynamodb_table_users,
                exc,
            )
        try:
            _seed_root_admin(
                user_repo=DynamoUserRepository(
                    table_name=settings.dynamodb_table_users
                ),
            )
            logger.info(
                "[lifespan] root admin garantido (%s)",
                settings.seed_admin_email,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[lifespan] falhou ao seedar admin: %s", exc)
    yield


app = FastAPI(title="Auth Service", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(well_known_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
