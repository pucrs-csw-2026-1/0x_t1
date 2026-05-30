# Dockerfile mínimo para o Auth Service.
#
# Objetivo: validar empacotamento da aplicação no CI/CD. Não inclui
# otimizações de produção (multi-stage, non-root user, healthcheck,
# wheels pre-built) — essas decisões ficam para iterações futuras
# quando houver infraestrutura AWS para deploy real.

FROM python:3.12-slim

# Metadata OCI (https://github.com/opencontainers/image-spec/blob/main/annotations.md)
LABEL org.opencontainers.image.title="Auth Service"
LABEL org.opencontainers.image.description="API de autenticação e autorização (OAuth2 + JWT) — Grupo 0x"
LABEL org.opencontainers.image.source="https://github.com/pucrs-csw-2026-1/0x_t1"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.licenses="Proprietary"
LABEL org.opencontainers.image.authors="Grupo 0x (PUCRS Construção de Software 2026/1)"

WORKDIR /app

# Instala dependências antes do código para aproveitar cache de layer
# entre builds que não alteram requirements.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação.
COPY app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
