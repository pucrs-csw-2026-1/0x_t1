# Bruno collection — auth-service

Coleção de smoke tests HTTP que exerce o app real contra a Ministack
(LocalStack/DynamoDB local). Complementa os testes de sistema em
[`backend/tests/test_system_auth_flow.py`](../backend/tests/test_system_auth_flow.py)
— enquanto o pytest roda no CI usando `mock_aws` (rápido), Bruno é a
camada manual de fidelidade total contra a stack que dev usa.

## ⚠️ Antes de tudo: selecionar o environment `Local`

**Toda variável (`{{baseUrl}}`, `{{email}}`, `{{seed_admin_email}}`, etc.)
só é resolvida se o environment `Local` estiver selecionado.** No Bruno:

1. `Open Collection` → aponta para a pasta `bruno/`.
2. No **canto superior direito**, clique no dropdown de environment.
3. Selecione `Local`.

Se você rodar um request sem isso, vai ver erros tipo "variável undefined"
ou requests batendo em URLs literais (`{{baseUrl}}/users/register` em vez
de `http://127.0.0.1:8000/users/register`). É a **primeira coisa pra checar**
quando algo falha.

## Pré-requisitos

1. Bruno instalado: <https://www.usebruno.com/>
2. Ministack rodando + tabelas criadas via Terraform
3. App FastAPI rodando localmente

## Como subir o ambiente

```bash
# 1) Ministack (na raiz do projeto)
cd terraform && docker compose up -d
terraform apply -auto-approve   # seed do catálogo access_level

# 2) App FastAPI
cd backend && uvicorn app.main:app --reload
# servirá em http://localhost:8000
```

O volume `.ministack-data/` configurado no compose mantém a tabela entre
restarts do container.

### Lifespan defensivo em `app_env=development`

Quando o app sobe em modo dev, dois bootstraps automáticos rodam:

1. **Tabela `user`** — criada se não existir (útil quando a Ministack foi
   recriada e ninguém lembrou de rodar `terraform apply`).
2. **Admin root** — criado se ainda não existir e o catálogo
   `access_level` estiver seedado. Credenciais: `admin@local.dev` /
   `Admin@123`. Login com elas devolve JWT com `scopes=["user", "admin"]`.

Isso **substitui o setup manual** via `aws dynamodb update-item` que existia
em versões anteriores. Pra promover **outros** usuários a admin, ver a
seção "Setup admin para pastas legacy" abaixo.

## Variáveis de ambiente

Definidas em [`environments/Local.bru`](environments/Local.bru). Divididas
em 4 grupos por persona/função:

### Usuário "juca" (pastas 01–08)

| Var | Valor / Origem | Tipo |
|---|---|---|
| `email`, `password`, `username`, `first_name`, `last_name` | `juca@email.com`, `Senha@123`, `juca.bala`, `Juca`, `Bala` (static) | var |
| `user_id` | populada por `01_Happy_Path/01_Register` | secret |
| `access_token`, `refresh_token` | populadas por `01_Happy_Path/02_Login` | secret |
| `next_cursor` | populada por `04_Admin_Listing/03` | secret |
| `deactivate_access_token` | populada por `07_Deactivate_Me/03` | secret |
| `target_user_id` | populada por `08_Admin_User_Management/01` | secret |

### Usuário "demo" (pasta 09_Demo_Completa)

| Var | Valor / Origem | Tipo |
|---|---|---|
| `demo_email`, `demo_password`, `demo_username`, `demo_first_name`, `demo_last_name` | `demo@svc.local`, `Demo@123`, `demo.user`, `Demo`, `User` (static) | var |
| `demo_user_id`, `demo_access_token`, `demo_refresh_token` | populadas por `09_Demo_Completa/01+02` | secret |

### Admin root (seedado pelo lifespan)

| Var | Valor / Origem | Tipo |
|---|---|---|
| `seed_admin_email`, `seed_admin_password` | `admin@local.dev`, `Admin@123` (static, batem com o seed) | var |
| `admin_access_token` | populada por `00_Setup_Admin/01_Login_Admin` | secret |
| `admin_user_id` | populada por `00_Setup_Admin/02_Get_Admin_Id` | secret |
| `seed_admin_access_token`, `seed_admin_user_id` | populadas por `09_Demo_Completa/12+13` (vars separadas para isolar o estado da demo) | secret |

### Constantes do catálogo

| Var | Valor |
|---|---|
| `admin_uuid` | `bace0701-15e3-5144-97c5-47487d543032` |
| `user_uuid` | `9e556479-7003-5916-9cd6-33f4227cec9b` |

São UUIDs deterministicos (uuidv5 com mesmo namespace que o seed do
Terraform). Disponíveis pra construir requests admin sem precisar olhar
o banco.

## Como rodar a collection

Folders por ordem, com dependência e isolamento:

| # | Folder | Cobertura | Dependência |
|---|---|---|---|
| 00 | [`00_Setup_Admin/`](00_Setup_Admin/) | login do admin root + captura do id | nenhuma — pré-requisito de 03/04/08 |
| 01 | [`01_Happy_Path/`](01_Happy_Path/) | register → login → me → refresh → logout | nenhuma |
| 02 | [`02_Errors/`](02_Errors/) | erros de cadastro/login/auth | 01 (pra ter `{{email}}` registrado) |
| 03 | [`03_Auth_Access/`](03_Auth_Access/) | US-13 admin scope gate | 00 + 01 |
| 04 | [`04_Admin_Listing/`](04_Admin_Listing/) | US-14 paginação admin | 00 + 2+ users no banco (rodar 01 antes) |
| 05 | [`05_Profile_Update/`](05_Profile_Update/) | US-15 PATCH `/users/me` | 01 (pra ter `{{access_token}}`) |
| 06 | [`06_Change_Password/`](06_Change_Password/) | US-16 troca de senha | 01 |
| 07 | [`07_Deactivate_Me/`](07_Deactivate_Me/) | US-17 desativação self | self-contido (cria user throwaway) |
| 08 | [`08_Admin_User_Management/`](08_Admin_User_Management/) | US-18 CRUD admin de usuários | 00 |
| 09 | [`09_Demo_Completa/`](09_Demo_Completa/) | end-to-end narrativo (US-01..US-18) | **self-contido** — cria seu próprio user/admin |

## O que cada pasta cobre

### `00_Setup_Admin/`

Bootstrapa o estado admin para as pastas 03/04/08. Rode os 2 requests em
sequência uma vez por sessão (re-rodar quando o token expirar — default
30min).

| # | Request | Espera |
|---|---|---|
| 01 | `POST /auth/login` como `admin@local.dev` | 200, popula `admin_access_token` |
| 02 | `GET /users/me` com `{{admin_access_token}}` | 200, popula `admin_user_id` |

O admin root é criado automaticamente pelo lifespan em
`app_env=development` — não precisa de promoção manual via DDB.

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

### `03_Auth_Access/` (US-13)

Cobre os critérios da US-13 (catálogo de perfis + scopes semânticos no JWT
+ atribuição segura no cadastro).

| # | Cenário | Espera |
|---|---|---|
| 01 | Register com `access_level: ["<UUID-admin>"]` no body | 201, mas response com `access_level=[<UUID-user>]` (descarte silencioso) |
| 02 | `/admin/ping` sem token | 401 "Token ausente" |
| 03 | `/admin/ping` com token de user normal | 403 "permissão insuficiente: requer 'admin'" |
| 04 | `/admin/ping` com token admin | 200 — precisa de `admin_access_token` |

### `04_Admin_Listing/` (US-14)

Listagem administrativa de usuários com paginação opaca por cursor. O
request 03 popula `next_cursor` via `script:post-response` e o 04 consome.

| # | Cenário | Espera |
|---|---|---|
| 01 | `GET /admin/users` sem token | 401 |
| 02 | `GET /admin/users` com token de user normal | 403 |
| 03 | `GET /admin/users?limit=1` com token admin | 200, popula `next_cursor` |
| 04 | `GET /admin/users?limit=1&cursor={{next_cursor}}` | 200, próxima página |

### `05_Profile_Update/` (US-15)

PATCH parcial em `/users/me` — atualizar profile sem re-cadastrar.

| # | Cenário | Espera |
|---|---|---|
| 01 | Register de segundo user (`conflito@example.com`) | 201 — pre-cadastro pro teste 05 |
| 02 | PATCH `first_name` e `last_name` | 200 |
| 03 | PATCH sem token | 401 |
| 04 | PATCH com email malformado | 422 |
| 05 | PATCH com email já cadastrado (do request 01) | 409 |

### `06_Change_Password/` (US-16)

PUT `/users/me/password` com defesa em profundidade (exige senha atual
mesmo com Bearer válido).

| # | Cenário | Espera |
|---|---|---|
| 01 | Troca para `NovaSenha@456` | 204 |
| 02 | Restaura para `{{password}}` original | 204 |
| 03 | Sem token | 401 |
| 04 | Senha atual incorreta | 401 |
| 05 | Nova senha igual à atual | 400 |
| 06 | Nova senha fraca | 422 |

> O par 01/02 (troca + restaura) é proposital pra manter `{{password}}`
> consistente após a pasta — outros folders ainda usam essa senha em logins.

### `07_Deactivate_Me/` (US-17)

Self-delete: marca `is_active=false`, revoga refresh tokens ativos e
bloqueia login subsequente. Usa user **throwaway** pra não derrubar o
juca e quebrar o flow.

| # | Cenário | Espera |
|---|---|---|
| 01 | `DELETE /users/me` sem token | 401 |
| 02 | Register throwaway (`desativar@example.com`) | 201 |
| 03 | Login throwaway | 200, popula `deactivate_access_token` |
| 04 | `DELETE /users/me` com `deactivate_access_token` | 204 |
| 05 | Login com as mesmas credenciais pós-delete | 401 |

### `08_Admin_User_Management/` (US-18)

CRUD admin em `/admin/users/{user_id}` — GET, PATCH (access_level e
is_active) e DELETE.

| # | Cenário | Espera |
|---|---|---|
| 01 | Register target user (`alvo.admin@example.com`) | 201, popula `target_user_id` |
| 02 | `GET /admin/users/{id}` | 200 |
| 03 | `GET` com UUID inexistente | 404 |
| 04 | `GET` com token de user normal | 403 |
| 05 | `PATCH` access_level (promove target a admin) | 200 |
| 06 | `PATCH` com UUID inexistente | 404 |
| 07 | `PATCH` access_level com UUID que não existe no catálogo | 422 |
| 08 | `DELETE` admin tentando deletar a si mesmo | 400 |
| 09 | `DELETE` com token de user normal | 403 |
| 10 | `DELETE` target user | 204 |
| 11 | `DELETE` com UUID inexistente | 404 |

### `09_Demo_Completa/` — fluxo narrativo end-to-end

Pensado pra **demo gravada**. 23 requests organizados em 5 capítulos
cobrindo todas as US (01 a 18). Self-contido: cria seu próprio user
(`demo@svc.local`), autentica via seed admin (`admin@local.dev`),
exercita features, encerra com logout.

| Capítulo | Reqs | Cobertura |
|---|---|---|
| **1. Cadastro & Auth** | 01-04 | register, login, get_me, refresh |
| **2. Erros de Auth** | 05-07 | senha fraca (400), email duplicado (409), senha errada (401) |
| **3. Self-Service** | 08-11 | US-15 PATCH profile (200 + 422), US-16 change password + restore |
| **4. Admin** | 12-20 | login seed admin, US-13 ping (200 + 403 gate), US-14 list, US-18 GET/PATCH (200 + 400 self + 404 + 422) |
| **5. Desativação** | 21-23 | US-17 self, login bloqueado (401), logout |

**Ordem importa:** o request 15 (admin ping com `demo_access_token` →
403 esperado) **precisa** rodar antes do 18 (promoção de `demo_user` a
admin). Após o 18 o demo ficaria com scopes `["user","admin"]` no banco,
mas só um login NOVO re-emite o JWT — o `demo_access_token` em mãos ainda
tem `["user"]`, daí o 403 do request 15 só funciona naquela janela.

**Pré-requisitos:**
- Ministack **zerada** pra re-rodar (`demo@svc.local` já cadastrado → 409
  no request 01). `docker compose down -v && terraform apply` reseta o
  volume.
- App rodando em `app_env=development` pra o seed admin existir.

## Promovendo outros usuários a admin

O `00_Setup_Admin/` cobre o caso comum (autenticar como o admin seedado).
Pra promover **outro** usuário (ex: dar admin a um user já cadastrado),
duas opções:

- **Via API** (preferida) — logado como admin, `PATCH /admin/users/{id}`
  com `{"access_level": ["<user_uuid>", "<admin_uuid>"]}`. Ver
  [`08_Admin_User_Management/05_Admin_Update_User_200.bru`](08_Admin_User_Management/05_Admin_Update_User_200.bru)
  como referência.
- **Via DDB direto** (último caso, debug) — `aws dynamodb update-item`.
  Lembrar de **substituir o placeholder `<USER_ID>` pelo id real** —
  rodar com `<USER_ID>` literal cria item órfão (vide "Limpando items
  órfãos" no troubleshooting).

Depois da promoção, exigir **login NOVO** do user: o JWT só herda scope
`admin` em logins emitidos após a mudança de `access_level`.

## Troubleshooting

| Sintoma | Causa provável | Como corrigir |
|---|---|---|
| `{{baseUrl}}` aparece literal na URL do request | Environment `Local` não selecionado | Canto superior direito → selecionar `Local` |
| 401 `Token ausente` em requests admin | Var `admin_access_token` (ou `seed_admin_access_token`) vazia ou expirada | Rodar `00_Setup_Admin/01` + `02` de novo |
| 401 `Token inválido` em requests admin | Token colado com `Bearer ` duplicado, aspas, ou espaço extra | Colar **só** o JWT cru (sem prefixo, sem aspas) |
| 401 `Token expirado` | Mais de 30min desde o login (default `access_token_expire_minutes`) | Re-rodar login e re-popular o token |
| 403 `requer 'admin'` | Token foi gerado **antes** da promoção (scopes=`["user"]`) | Refazer login pós-promoção. Decoda em jwt.io pra conferir scopes |
| 500 `KeyError: 'email'` em `/admin/users` | Item órfão na tabela (provável `update-item` com `<USER_ID>` literal, criando `id=""`) | Identificar e deletar o item parcial (vide próxima subseção) |
| 409 no `09_Demo_Completa/01` no re-run | `demo@svc.local` já cadastrado em run anterior | `docker compose down -v && terraform apply` pra zerar |
| Lifespan log `falhou ao seedar admin` | Catálogo `access_level` vazio (terraform não rodou) | `cd terraform && terraform apply -auto-approve` antes de re-iniciar uvicorn |

### Limpando items órfãos

Se um `update-item` foi rodado com placeholder não substituído, sobra um
item parcial no banco que quebra a listagem. Identifica com scan completo
procurando items com `id` vazio ou sem `email`:

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

Pra rodar só uma pasta (ex.: a demo):

```bash
bru run --env Local 09_Demo_Completa
```

Útil pra integrar num smoke test pós-deploy.
