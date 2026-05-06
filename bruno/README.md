# Bruno collection — auth-service

Coleção de smoke tests HTTP que exerce o app real contra a Ministack
(LocalStack/DynamoDB local). Complementa os testes de sistema em
[`backend/tests/test_system_auth_flow.py`](../backend/tests/test_system_auth_flow.py)
— enquanto o pytest roda no CI usando `mock_aws` (rápido), Bruno é a
camada manual de fidelidade total contra a stack que dev usa.

## Pré-requisitos

1. Bruno instalado: <https://www.usebruno.com/>
2. Ministack rodando + tabela criada via Terraform
3. App FastAPI rodando localmente

## Como subir o ambiente

```bash
# 1) Ministack (na raiz do projeto)
cd terraform && docker compose up -d

# 2) App FastAPI — em app_env=development o lifespan cria a tabela
#    automaticamente se ela não existir (defensive bootstrap).
cd backend && uvicorn app.main:app --reload
# servirá em http://localhost:8000
```

> Para provisionar via IaC explicitamente (recomendado em time/CI),
> rode `cd terraform && terraform init && terraform apply -auto-approve`
> antes do passo 2. O volume `.ministack-data/` configurado no
> compose mantém a tabela entre restarts do container.

## Como rodar a collection

1. Abrir Bruno → `Open Collection` → apontar para esta pasta `bruno/`
2. Selecionar o environment `Local` no canto superior direito
3. Rodar os requests **na ordem**:
   - `01_Happy_Path/` — fluxo encadeado, cada request usa vars setadas pelo anterior
   - `02_Errors/` — variantes de erro (alguns dependem do happy path para 409 e senha errada)

## O que cada pasta cobre

### `01_Happy_Path/`

Sequência ponta-a-ponta. As vars `access_token`, `refresh_token` e
`user_id` são populadas pelos `script:post-response` e usadas nos
requests seguintes.

| # | Request | Espera |
|---|---|---|
| 01 | `POST /users/register` | 201, popula `user_id` |
| 02 | `POST /auth/login` | 200, popula `access_token` + `refresh_token` |
| 03 | `GET /users/me` (Bearer) | 200, retorna user |
| 04 | `POST /auth/refresh` | 200, atualiza `access_token` |
| 05 | `POST /auth/logout` (Bearer + body) | 204 |
| 06 | `POST /auth/refresh` (mesmo refresh) | 401 "revogado" — regressão do bug do logout |

### `02_Errors/`

Pega os ramos de erro do mapa `domain → HTTP`:

| # | Cenário | Espera |
|---|---|---|
| 01 | Register email duplicado | 409 |
| 02 | Register email malformado | 400 |
| 03 | Register senha fraca | 400 |
| 04 | Login senha errada | 401 |
| 05 | Login email inexistente | 401 |
| 06 | Login email malformado | 401 (não 400 — sem enumeração) |
| 07 | `/users/me` sem token | 401 "Token ausente" |
| 08 | `/auth/logout` sem token | 401 "Token ausente" — confusão típica do Swagger |

## CLI (opcional)

Se quiser rodar a collection toda no terminal:

```bash
npm install -g @usebruno/cli
cd bruno && bru run --env Local
```

Útil pra integrar num smoke test pós-deploy.
