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
   - `03_Auth_Access/` — autorização por escopo (gate de admin, descarte de auto-promoção)
   - `04_Admin_Listing/` — listagem administrativa de usuários (paginação)

> Os requests admin (`03_Auth_Access/04`, todos do `04_Admin_Listing/`) dependem da
> var `admin_access_token`, que **não é populada automaticamente**. Rode o
> setup abaixo uma vez por Ministack antes desses cenários.

## Setup admin (uma vez por Ministack)

A API pública não permite cadastrar admin (US-13: auto-promoção é
silenciosamente descartada). Para exercer rotas admin no Bruno, precisa
promover um user manualmente no DynamoDB Local e copiar o token gerado
para a var de environment.

### Passo a passo

1. **Registrar user normal** — rode `01_Happy_Path/01_Register.bru`. O
   `script:post-response` salva o `user_id` na env Local.

2. **Capturar o `user_id`** — abre o Environment no Bruno (canto superior
   direito → Configure → Secrets) e copia o valor de `user_id`.

3. **Promover esse user** — substitua `<USER_ID>` pelo valor copiado e
   rode no terminal (bash ou Git Bash):

   ```bash
   aws --endpoint-url=http://localhost:4566 dynamodb update-item \
     --table-name user \
     --key '{"id":{"S":"<USER_ID>"}}' \
     --update-expression "SET access_level = :a" \
     --expression-attribute-values '{":a":{"L":[{"S":"9e556479-7003-5916-9cd6-33f4227cec9b"},{"S":"bace0701-15e3-5144-97c5-47487d543032"}]}}'
   ```

   ⚠️ **Não esqueça de substituir o placeholder** — rodar com `<USER_ID>`
   literal cria um item órfão na tabela com `id=""` e quebra `GET /admin/users`
   com 500 (vide Troubleshooting). Os UUIDs no comando são `user_uuid` e
   `admin_uuid` do catálogo (já em `Local.bru`).

4. **Confirmar a promoção** — espera ver `access_level` com os 2 UUIDs:

   ```bash
   aws --endpoint-url=http://localhost:4566 dynamodb get-item \
     --table-name user --key '{"id":{"S":"<USER_ID>"}}'
   ```

5. **Login NOVO** — rode `01_Happy_Path/02_Login.bru` de novo. O JWT antigo
   ainda tem `scopes=["user"]` — o token só herda `admin` em logins **após**
   a promoção (o `JwtTokenProvider` lê `access_level` atual do banco a cada
   login).

6. **Copiar o `access_token` para `admin_access_token`** — no Bruno:
   Environment Local → Configure → Secrets → cole o valor do
   `access_token` (vindo do response do passo 5) na entrada
   `admin_access_token`. Salva. Agora os requests admin funcionam.

> Decoda o JWT em <https://jwt.io> antes de colar — o payload deve ter
> `"scopes": ["user", "admin"]` (ou ordem inversa). Se só tiver `["user"]`,
> a promoção não pegou ou você fez login antes do passo 3.

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

### `03_Auth_Access/`

Cobre os critérios da US-13 (catálogo de perfis + scopes semânticos no JWT
+ atribuição segura no cadastro).

| # | Cenário | Espera |
|---|---|---|
| 01 | Register com `access_level: ["<UUID-admin>"]` no body | 201, mas response com `access_level=[<UUID-user>]` (descarte silencioso) |
| 02 | `/admin/ping` sem token | 401 "Token ausente" |
| 03 | `/admin/ping` com token de user normal | 403 "permissão insuficiente: requer 'admin'" |
| 04 | `/admin/ping` com token admin | 200 — **manual**, requer promoção via DDB (vide doc do request) |

Os UUIDs do catálogo (`admin_uuid`, `user_uuid`) ficam no environment
`Local.bru` e são determinísticos (uuid v5 do mesmo namespace que o
seed do Terraform).

### `04_Admin_Listing/`

Cobre os critérios da US-14 (listagem administrativa de usuários com
paginação opaca por cursor). O request 03 popula a var `next_cursor`
via `script:post-response` e o request 04 consome para avançar.

| # | Cenário | Espera |
|---|---|---|
| 01 | `GET /admin/users` sem token | 401 |
| 02 | `GET /admin/users` com token de user normal | 403 |
| 03 | `GET /admin/users?limit=1` com token admin | 200, popula `next_cursor` |
| 04 | `GET /admin/users?limit=1&cursor={{next_cursor}}` | 200, próxima página |

Os requests 03 e 04 dependem de `admin_access_token` (mesma promoção
manual usada em `03_Auth_Access/04`) e de pelo menos 2 users no banco
(rode `01_Happy_Path/01_Register.bru` antes se necessário).

## Troubleshooting

Erros recorrentes em smoke tests admin:

| Sintoma | Causa provável | Como corrigir |
|---|---|---|
| 401 `Token ausente` | Var `admin_access_token` vazia (login não copiado pra env). | Refazer passo 6 do setup admin. |
| 401 `Token inválido` | Valor colado com `Bearer ` duplicado, aspas, ou espaço extra. | Colar **só** o JWT cru (sem prefixo, sem aspas). |
| 401 `Token expirado` | Mais de 30min desde o login (default `access_token_expire_minutes`). | Rodar `01_Happy_Path/02_Login.bru` de novo + refazer passo 6. |
| 403 `requer 'admin'` | Token foi gerado **antes** da promoção (scopes=`["user"]`). | Refazer login pós-promoção (passo 5). Decoda em jwt.io para conferir. |
| 500 `KeyError: 'email'` em `/admin/users` | Item órfão na tabela (provável `update-item` com `<USER_ID>` não substituído, criando `id=""`). | Identificar e deletar o item parcial — vide próxima subseção. |
| `GET /admin/users` retorna 1 item com `next_cursor` populado | Esperado: o request 03 usa `?limit=1` para forçar paginação. | Rodar `04_Admin_Listing/04` em sequência para avançar páginas, ou aumentar o `limit`. |

### Limpando items órfãos

Se um `update-item` foi rodado com placeholder não substituído, sobra um
item parcial no banco que quebra a listagem. Identifica com scan completo
e procura items com `id` vazio ou sem `email`:

```bash
aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name user
```

Deleta o item órfão (ajuste o id conforme aparece no scan):

```bash
aws --endpoint-url=http://localhost:4566 dynamodb delete-item \
  --table-name user --key '{"id":{"S":""}}'
```

## CLI (opcional)

Se quiser rodar a collection toda no terminal:

```bash
npm install -g @usebruno/cli
cd bruno && bru run --env Local
```

Útil pra integrar num smoke test pós-deploy.
