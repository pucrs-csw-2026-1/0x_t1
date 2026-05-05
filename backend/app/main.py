from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Carrega .env em os.environ antes do boto3 instanciar clientes,
# para que AWS_ENDPOINT_URL/credenciais apontem ao Ministack em dev.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.adapters.api.auth_router import router as auth_router  # noqa: E402
from app.adapters.api.user_router import router as user_router  # noqa: E402

app = FastAPI(title="Auth Service", version="0.1.0")

app.include_router(auth_router)
app.include_router(user_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
