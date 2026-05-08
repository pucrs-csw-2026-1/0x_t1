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
from app.adapters.config.settings import settings  # noqa: E402
from app.adapters.dynamo_user_repository import DynamoUserRepository  # noqa: E402

logger = logging.getLogger(__name__)


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
    yield


app = FastAPI(title="Auth Service", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
