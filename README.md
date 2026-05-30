# Auth Service — API de Autenticação e Autorização

Serviço RESTful responsável pelo cadastro de usuários, autenticação via **OAuth2**, emissão de tokens de acesso (JWT) e validação de permissões. Construído com **FastAPI**, **Pydantic v2** e **DynamoDB**, seguindo **Arquitetura Hexagonal** (Ports and Adapters).

> Trabalho da disciplina de **Construção de Software** — PUCRS, 2026/1 · Grupo **0x**.

### Autores — Grupo 0x

- Carlos Eduardo B. Mascarello
- Lucas A. Brentano
- Victória C. Marques

---

## Índice

1. [Visão Geral](#visão-geral)
2. [Funcionalidades](#funcionalidades)
3. [Tech Stack](#tech-stack)
4. [Arquitetura Hexagonal](#arquitetura-hexagonal)
5. [Estrutura do Projeto](#estrutura-do-projeto)
6. [Configuração e Instalação](#configuração-e-instalação)
7. [Executando a Aplicação](#executando-a-aplicação)
8. [Modelagem do Banco de Dados](#modelagem-do-banco-de-dados)
9. [Segurança — OAuth2 + JWT](#segurança--oauth2--jwt)
10. [Referência de Endpoints](#referência-de-endpoints)
11. [Testes](#testes)
12. [Linting e Tipagem](#linting-e-tipagem)
13. [Controle de Versões e CI/CD](#controle-de-versões-e-cicd)
14. [FAQ e Troubleshooting](#faq-e-troubleshooting)

---

## Visão Geral

### O quê

O Auth Service é um microsserviço de identidade focado em **autenticação** e **controle de acesso baseado em escopos**. Sua responsabilidade é única: validar quem é o usuário (credenciais → tokens JWT) e emitir os escopos que permitem ou bloqueiam o acesso a recursos protegidos.

O design segue **Arquitetura Hexagonal** estrita: o domínio (entidades, value objects, regras de validação de senha/email/username) não conhece banco, framework ou HTTP. Toda integração externa passa por **ports** (ABCs do Python) implementadas por **adapters** trocáveis — DynamoDB hoje pode virar Postgres amanhã, bcrypt pode virar argon2, JWT pode virar tokens opacos, sem tocar nas regras de negócio.

### Para quem

Três tipos de consumidor estão previstos:

- **Usuários finais** acessando via cliente HTTP (web ou mobile) — cadastram-se, autenticam-se, atualizam o próprio perfil e podem desativar a própria conta.
- **Administradores** com escopo `admin` no JWT — listam usuários, alteram níveis de acesso e desativam contas alheias. O sistema impede o admin de desativar a si mesmo (retorna `400`) para evitar lockout do próprio painel.
- **Outros serviços** (uso futuro) — validam tokens emitidos por este serviço via verificação de assinatura JWT, sem precisar consultar a base de usuários a cada requisição.

### Quais limites

Estão **fora do escopo** desta implementação:

- **MFA / 2FA** — apenas senha + email.
- **OAuth social** (login com Google, GitHub etc.) — apenas OAuth2 Password Bearer interno.
- **Gestão de organizações, times ou permissões compostas** — o modelo de autorização usa um papel único por usuário (`access_level`: enum `PARTICIPANT`/`MANAGER`/`ADMIN`, cumulativo), não uma árvore de permissões ortogonais.
- **Recuperação de senha por email** — não há fluxo de "esqueci minha senha"; a troca exige sempre a senha atual.
- **Rate limiting, auditoria detalhada e observabilidade** — responsabilidade da camada de infraestrutura.
- **Deploy em produção** — todo o setup atual visa desenvolvimento local com Terraform + LocalStack. O pipeline de CD está documentado mas o step de deploy AWS ainda está pendente.

---

## Funcionalidades

Cada feature abaixo cita a User Story (US) que a implementou.

### Cadastro e Autenticação

| Funcionalidade | US | Endpoint |
|---|---|---|
| Cadastro público de usuário (senha armazenada com hash bcrypt) | US-04, US-09 | `POST /users/register` |
| Login OAuth2 Password Bearer (com emissão de access + refresh tokens JWT) | US-05, US-06 | `POST /auth/login` |
| Renovação de access token via refresh token | US-07 | `POST /auth/refresh` |
| Logout (revogação de refresh) | US-08 | `POST /auth/logout` |

### Autorização

| Funcionalidade | US | Detalhe |
|---|---|---|
| Proteção de rotas por Bearer token | US-11 | `Depends(get_current_user)` em todas as rotas privadas |
| Controle de acesso por perfil (scopes no JWT) | US-12 | `Security(get_current_user, scopes=["admin"])` em rotas privilegiadas; 403 quando o token não tem o scope exigido |
| Papel único por usuário e scope gate `admin` | US-13, US-27 | `access_level` é um enum (`PARTICIPANT`/`MANAGER`/`ADMIN`) com scopes cumulativos; tentativa de auto-promoção no cadastro é silenciosamente descartada |

### Self-Service do Perfil

| Funcionalidade | US | Endpoint |
|---|---|---|
| Consultar perfil próprio | US-10 | `GET /users/me` |
| Atualizar perfil (`first_name`, `last_name`, `email`, `username`) | US-15 | `PATCH /users/me` |
| Trocar senha (exige senha atual + valida força da nova) | US-16 | `PUT /users/me/password` |
| Desativar a própria conta (soft delete; novos logins **e refreshes** falham com 401) | US-17 | `DELETE /users/me` |

### Administração

| Funcionalidade | US | Endpoint |
|---|---|---|
| Listagem paginada por cursor opaco | US-14 | `GET /admin/users?limit=N&cursor=X` |
| Consultar usuário por ID | US-18 | `GET /admin/users/{user_id}` |
| Atualizar `access_level` ou `is_active` de outro usuário | US-18 | `PATCH /admin/users/{user_id}` |
| Desativar outro usuário (admin não desativa a si mesmo → 400) | US-18 | `DELETE /admin/users/{user_id}` |

### Qualidade

| Funcionalidade | US | Detalhe |
|---|---|---|
| Mensagens de erro claras e padronizadas | US-02 | Mapeamento das exceções de domínio para status HTTP semânticos (400, 401, 403, 404, 409, 422, 500). `detail` em português, sem vazar stack trace ou identidade interna |

> A configuração do ambiente de desenvolvimento (Terraform + LocalStack, tratada pelo time como "story-zero" sem issue numerada), a **US-01** (entidade `User` e value objects validados no domínio) e a **US-03** (port `UserRepository` e adapter DynamoDB para persistência) cobriram a camada de infraestrutura compartilhada. Detalhes na seção [Arquitetura Hexagonal](#arquitetura-hexagonal).

---

## Tech Stack

| Camada | Tecnologia |
|---|---|
| Framework web | [FastAPI](https://fastapi.tiangolo.com/) |
| Linguagem | Python 3.12+ |
| Validação e schemas | [Pydantic v2](https://docs.pydantic.dev/latest/) |
| Configuração | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Tipagem estática | [mypy](https://mypy-lang.org/) |
| Linter / Formatter | [Ruff](https://docs.astral.sh/ruff/) |
| Testes | [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) + [httpx](https://www.python-httpx.org/) |
| Mock DynamoDB | [moto](https://docs.getmoto.org/en/latest/) |
| Banco de dados | [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) via [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) |
| Autenticação | OAuth2 (FastAPI) + JWT ([python-jose](https://python-jose.readthedocs.io/)) + bcrypt ([passlib](https://passlib.readthedocs.io/)) |

---

## Arquitetura Hexagonal

O projeto segue a **Arquitetura Hexagonal** (Ports and Adapters), separando o domínio da infraestrutura e permitindo que adaptadores sejam substituídos sem afetar a lógica de negócio.

![Arquitetura Hexagonal — `domain/` dentro de `application/` dentro de `ports/`, com adapters externos](./t1_construcao.drawio.svg)

**Legenda:**

- **Hexágonos aninhados** (do mais interno ao mais externo): `domain/` ⊂ `application/` ⊂ `ports/`. Vale a regra clássica de Clean / Hexagonal Architecture — a camada externa enxerga a interna, **nunca o contrário** — daí a seta `usa` apontar de `application/` para `domain/` (e não o oposto).
- **Setas sólidas** (`chama`, `usa`) — chamada direta entre camadas no fluxo normal de execução.
- **Setas tracejadas com cabeça vazia** (`implementa`) — realização de interface (estilo UML). O adapter concreto implementa a ABC declarada em `ports/`.
- **Cores:** verde = driving adapter (entrada HTTP), amarelo = driven adapters (saída via ports), roxo/laranja/azul = camadas internas do core.

### Ports e ABC (Abstract Base Class)

Os **ports** são interfaces definidas como **ABC** (`abc.ABC` + `@abstractmethod`) — a forma nativa do Python de declarar contratos abstratos. Qualquer adapter que herde de um port é obrigado a implementar todos os métodos, caso contrário o Python lança `TypeError` ao instanciar.

```python
from abc import ABC, abstractmethod

# Port (interface abstrata)
class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...

# Adapter (implementação concreta)
class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return bcrypt.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.verify(password, hashed)
```

Isso garante o **Dependency Inversion Principle**: os use cases dependem da ABC `PasswordHasher`, nunca de `BcryptPasswordHasher` diretamente. Se amanhã trocarmos bcrypt por argon2, basta criar um novo adapter — sem alterar nenhum use case.

### Padrões de Projeto Utilizados

| Padrão | Onde | Como funciona no projeto |
|---|---|---|
| **Repository** | `ports/user_repository.py` -> `adapters/dynamo_user_repository.py` | ABC define `save`, `find_by_email`, `find_by_id`. O adapter implementa via boto3/DynamoDB. Os use cases usam a interface, sem saber que o banco é DynamoDB |
| **Strategy** | `ports/password_hasher.py` -> `adapters/bcrypt_password_hasher.py` | ABC define `hash` e `verify`. O adapter implementa com bcrypt. Pode ser trocado por argon2 sem alterar use cases. Mesmo princípio para `TokenProvider` (JWT hoje, pode ser opaco amanhã) |
| **Dependency Injection** | `adapters/api/dependencies.py` | FastAPI `Depends()` injeta as implementações concretas nos routers. As factories em `dependencies.py` (`get_user_service`, `get_auth_service`) montam o grafo (qual adapter satisfaz qual port) |
| **DTO (Data Transfer Object)** | `adapters/api/auth_router.py`, `user_router.py` | Schemas Pydantic (`UserCreate`, `UserResponse`, `TokenResponse`) desacoplam a entrada/saída HTTP das entidades de domínio |

---

## Estrutura do Projeto

```
/
├── backend/
│   ├── app/
│   │   ├── main.py                          # Ponto de entrada FastAPI + lifespan (seed admin em dev)
│   │   │
│   │   ├── domain/                          # Camada de Domínio (sem deps externas)
│   │   │   ├── user.py                      # Entidade User + value objects (Email, Username, HashedPassword)
│   │   │   ├── access_level.py              # Enum Role + mapa cumulativo de scopes
│   │   │   └── exceptions.py                # Exceções de domínio
│   │   │
│   │   ├── ports/                           # Portas de saída (interfaces ABC)
│   │   │   ├── user_repository.py           # Interface: UserRepository
│   │   │   ├── token_provider.py            # Interface: TokenProvider
│   │   │   ├── password_hasher.py           # Interface: PasswordHasher
│   │   │   └── refresh_token_repository.py  # Interface: RefreshTokenRepository
│   │   │
│   │   ├── application/                     # Camada de Aplicação (Use Cases)
│   │   │   ├── auth_service.py              # Login, refresh, logout
│   │   │   └── user_service.py              # Cadastro, perfil, troca de senha, deactivate, admin CRUD
│   │   │
│   │   └── adapters/                        # Adaptadores (infraestrutura)
│   │       ├── api/                         # Driving Adapters (FastAPI)
│   │       │   ├── auth_router.py           # Rotas /auth/* (OAuth2 + schemas de tokens)
│   │       │   ├── user_router.py           # Rotas /users/* (cadastro, /me, troca senha, deactivate)
│   │       │   ├── admin_router.py          # Rotas /admin/* (listing + CRUD admin, gate por scope)
│   │       │   └── dependencies.py          # OAuth2PasswordBearer, get_current_user, factories
│   │       ├── config/
│   │       │   └── settings.py              # Settings via pydantic-settings (BaseSettings)
│   │       ├── dynamo_user_repository.py    # UserRepository -> DynamoDB (boto3)
│   │       ├── in_memory_refresh_token_repository.py  # RefreshTokenRepository in-memory (dev)
│   │       ├── jwt_token_provider.py        # TokenProvider -> python-jose
│   │       └── bcrypt_password_hasher.py    # PasswordHasher -> passlib/bcrypt
│   │
│   ├── tests/
│   │   ├── conftest.py                      # Fixtures globais e dubles reutilizáveis
│   │   ├── fakes/                           # In-memory test doubles dos ports
│   │   ├── test_auth_service.py             # Use case de autenticação
│   │   ├── test_user_service.py             # Use case de usuários
│   │   ├── test_domain.py                   # Entidades e value objects
│   │   ├── test_token_provider.py           # Geração/validação JWT
│   │   ├── test_password_hasher.py          # Hashing bcrypt
│   │   ├── test_user_repository.py          # Adapter DynamoDB (moto)
│   │   ├── test_auth_router.py              # Rotas /auth/*
│   │   ├── test_user_router.py              # Rotas /users/*
│   │   ├── test_admin_router.py             # Rotas /admin/*
│   │   ├── test_dependencies.py             # get_current_user, require_scope
│   │   ├── test_route_auth_audit.py         # Auditoria de quais rotas exigem token
│   │   └── test_system_auth_flow.py         # Fluxo ponta-a-ponta (register -> login -> me -> refresh -> logout)
│   │
│   ├── .env.example                         # Exemplo de variáveis de ambiente
│   ├── pyproject.toml                       # Dependências, mypy e Ruff
│   ├── requirements.txt                     # Dependências de produção
│   └── requirements-dev.txt                 # Dependências de desenvolvimento
│
├── bruno/                                   # Smoke tests HTTP (coleção Bruno) + environments
├── terraform/                               # IaC (LocalStack + DynamoDB) + diagrama do banco (db_model.png)
├── .github/                                 # Workflows CI/CD (ci, cd, pr-gate, sync-dev)
├── .ai_log/                                 # Logs dos prompts de IA usados no desenvolvimento (req. da disciplina)
├── t1_construcao.drawio.svg                 # Diagrama da arquitetura hexagonal (exportado do draw.io)
├── CONTRIBUTING.md                          # Regras de contribuição (GitFlow + Conventional Commits)
├── TESTING.md                               # Estratégia de testes unitários (dubles, técnicas, cobertura)
└── README.md
```

---

## Configuração e Instalação

### Pré-requisitos

- Python 3.12+
- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- [Terraform](https://developer.hashicorp.com/terraform/downloads) `>= 1.5`
- (Opcional) [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) para inspecionar o DynamoDB local

### 1. Clone e entre no diretório

```bash
git clone https://github.com/pucrs-csw-2026-1/0x_t1.git
cd backend
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
source .venv/Scripts/activate      # Windows (Git Bash / MINGW64)
.venv\Scripts\activate             # Windows (cmd / PowerShell)
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt        # produção
pip install -r requirements-dev.txt    # ferramentas de dev/test
```

### 4. Configure as variáveis de ambiente

Copie `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

```dotenv
# .env.example
APP_ENV=development
SECRET_KEY=changeme            # legado HS256; não mais usado (ver RS256 abaixo)
ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# RS256 (US-28) — par de chaves para assinar/validar os JWTs.
# Em dev aponta para o par versionado em backend/keys/ (dev-only).
RSA_PRIVATE_KEY_PATH=keys/dev_private.pem
RSA_PUBLIC_KEY_PATH=keys/dev_public.pem
JWT_KID=auth-dev-key

AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566   # Ministack (LocalStack-like)
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

DYNAMODB_TABLE_USERS=user
```

A configuração é carregada via `pydantic-settings` (`BaseSettings`), com validação automática de tipos e valores:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str | None = None          # legado HS256 (não usado)
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    rsa_private_key_path: str = "keys/dev_private.pem"
    rsa_public_key_path: str = "keys/dev_public.pem"
    jwt_kid: str = "auth-dev-key"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    dynamodb_table_users: str = "user"

    model_config = SettingsConfigDict(env_file=".env")
```

### 5. Suba o Ministack e provisione as tabelas

A stack DynamoDB roda localmente via Docker Compose (Ministack) e é provisionada por Terraform. Da raiz do projeto:

```bash
cd terraform
docker compose up -d
terraform init   # primeira vez ou após mudar providers
terraform apply
```

Para detalhes (verificação, encerramento, persistência), veja [terraform/README.md](terraform/README.md).

---

## Executando a Aplicação

Há dois modos suportados: **uvicorn local** (recomendado para desenvolvimento iterativo, com auto-reload) e **container Docker** (espelha o ambiente do CI/CD).

### Modo 1 — uvicorn local (dev iterativo)

```bash
cd backend
uvicorn app.main:app --reload
```

> Porta padrão do uvicorn é `8000`. O Ministack roda em `4566`, sem conflito. O `--reload` reinicia o servidor automaticamente quando arquivos em `app/` são modificados.

### Modo 2 — Container Docker

Pré-requisitos: LocalStack rodando (`cd terraform && docker compose up -d`) e Terraform aplicado.

**Build da imagem** (do diretório raiz do projeto):

```bash
docker build -t auth-service:dev -f backend/Dockerfile backend/
```

**Run do container:**

```bash
docker run --rm -it \
  --name auth-service \
  -p 8080:8080 \
  --env-file backend/.env \
  -e AWS_ENDPOINT_URL=http://host.docker.internal:4566 \
  --add-host=host.docker.internal:host-gateway \
  auth-service:dev
```

Decodificando as flags:

- `--name auth-service` — nome fixo do container (permite `docker logs auth-service`, `docker stop auth-service`, etc.).
- `-p 8080:8080` — mapeia a porta 8080 do container para a porta 8080 do host.
- `--env-file backend/.env` — passa todas as variáveis do `.env` para o container (`SECRET_KEY`, `APP_ENV`, etc.).
- `-e AWS_ENDPOINT_URL=...` — **sobrescreve** o endpoint do LocalStack: dentro do container, `localhost` aponta para o próprio container, então é necessário usar `host.docker.internal` para acessar o LocalStack que está no host.
- `--add-host=host.docker.internal:host-gateway` — necessário em Linux (no Docker Desktop em Windows/macOS é automático).
- `--rm -it` — remove o container ao parar e roda em modo interativo (logs aparecem no terminal).

**Operações comuns no container:**

```bash
docker ps --filter "name=auth-service"   # verifica se está rodando
docker logs auth-service                 # ver logs (se rodou sem --rm)
docker stop auth-service                 # parar (Ctrl+C também funciona com -it)
```

### Documentação interativa

Em qualquer um dos modos, a documentação interativa estará disponível em:

- Swagger UI: <http://localhost:8080/docs>
- ReDoc: <http://localhost:8080/redoc>

---

## Modelagem do Banco de Dados

O serviço utiliza **Amazon DynamoDB** como banco de dados NoSQL. A modelagem foi projetada para suportar autenticação, controle de acesso e gerenciamento de usuários com eficiência.

![Modelo do Banco de Dados](./terraform/db_model.png)

### Tabelas

| Tabela | Partition Key | Descrição |
|---|---|---|
| `user` | `id` (UUID) | Armazena usuários cadastrados no sistema |

### Decisões de Modelagem

- O atributo `access_level` em `user` é um **papel único** (string enum `PARTICIPANT`/`MANAGER`/`ADMIN`), gravado no próprio registro. A partir da US-27 não há mais tabela de catálogo nem FK lógica — o papel é um tipo no código e os scopes do JWT são derivados dele de forma cumulativa.
- Palavras reservadas do DynamoDB (como `name`) foram substituídas por alternativas semânticas equivalentes para evitar conflitos em expressões de consulta.

---

## Segurança — OAuth2 + JWT

O serviço implementa o fluxo **OAuth2 Password Bearer** nativo do FastAPI:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
```

- **Login** (`POST /auth/login`): recebe credenciais via `OAuth2PasswordRequestForm`, valida e retorna access + refresh tokens JWT.
- **Rotas protegidas**: utilizam `Depends(get_current_user)`, que extrai e valida o token Bearer automaticamente.
- **Escopos**: permissões granulares via `Security(get_current_user, scopes=["admin"])`.

### Assinatura dos tokens — RS256 + JWKS (US-28)

Os JWTs são assinados em **RS256** (assimétrico): o Auth assina com a **chave privada** e qualquer consumidor valida com a **chave pública**, publicada em `GET /.well-known/jwks.json`. Isso permite que outros microserviços (ex.: Metrics) validem os tokens **sem compartilhar segredo** — diferente do HS256 simétrico anterior, em que todo serviço precisaria da mesma chave para validar (e poderia forjar tokens).

- O header de cada token traz um `kid`; o consumidor casa esse `kid` com a chave do JWKS.
- Todo token carrega o claim `principal_type`: `user` (pessoa, via login) ou `service` (máquina, via OAuth2 **client_credentials** em `POST /auth/token` — o serviço autentica com `client_id`/`client_secret` e recebe um token com os scopes do cliente, sem refresh).
- **Chaves**: em dev, par RS256 versionado em [`backend/keys/`](backend/keys/) (dev-only). Em produção, monte chaves de um cofre de segredos (AWS Secrets Manager — US-23) via `RSA_PRIVATE_KEY_PATH`/`RSA_PUBLIC_KEY_PATH`; a chave privada de produção nunca é commitada.

### Ciclo de vida dos tokens (login → uso → refresh → logout)

```mermaid
sequenceDiagram
    actor Cliente
    participant API as Auth Service
    participant DDB as DynamoDB
    participant Mem as InMemoryRefresh<br/>TokenRepo

    rect rgba(213, 232, 212, 0.4)
        Note over Cliente,Mem: Fase 1 — Login (emissão de tokens)
        Cliente->>API: POST /auth/login<br/>(email + password)
        API->>DDB: find_by_email(email)
        DDB-->>API: user record
        API->>API: bcrypt.verify(password, user.hashed_password)
        API->>API: gera access_token (JWT, exp = 30min)
        API->>API: gera refresh_token (JWT, exp = 7 dias)
        API-->>Cliente: 200 {access_token, refresh_token, token_type}
    end

    rect rgba(218, 232, 252, 0.4)
        Note over Cliente,Mem: Fase 2 — Uso de rotas protegidas
        Cliente->>API: GET /users/me<br/>Authorization: Bearer <access>
        API->>API: decode JWT (assinatura + exp + scopes)
        API->>DDB: find_by_id(sub)
        DDB-->>API: user record
        API-->>Cliente: 200 {user data}
    end

    rect rgba(255, 230, 204, 0.4)
        Note over Cliente,Mem: Fase 3 — Refresh (antes do access expirar)
        Cliente->>API: POST /auth/refresh<br/>{refresh_token}
        API->>Mem: is_revoked(refresh)?
        Mem-->>API: false
        API->>API: decode refresh + emite novo access
        API-->>Cliente: 200 {new access_token}
    end

    rect rgba(248, 206, 204, 0.4)
        Note over Cliente,Mem: Fase 4 — Logout (revogação do refresh)
        Cliente->>API: POST /auth/logout<br/>Bearer + {refresh_token}
        API->>API: valida access (header)
        API->>Mem: revoke(refresh_token)
        Mem-->>API: ok
        API-->>Cliente: 204

        Cliente->>API: POST /auth/refresh<br/>(mesmo refresh)
        API->>Mem: is_revoked(refresh)?
        Mem-->>API: true
        API-->>Cliente: 401 'Refresh token revogado'
    end
```

### Gate de autorização (Bearer + scope check)

Como cada request protegido é validado, antes de chegar no handler do endpoint. Mapeia diretamente o que `get_current_user` (em [`backend/app/adapters/api/dependencies.py`](backend/app/adapters/api/dependencies.py)) faz internamente para US-11 (Bearer obrigatório) e US-12 (scope obrigatório).

```mermaid
flowchart TD
    request[Cliente envia request<br/>com Authorization: Bearer JWT]
    has_header{Header<br/>presente?}
    extract[Extrai token via<br/>OAuth2PasswordBearer]
    decode[decode_token<br/>valida assinatura + exp]
    sub_check{Payload<br/>tem 'sub'?}
    scopes_required{Endpoint requer<br/>scope específico?}
    scope_in_jwt{Scope no<br/>payload do JWT?}
    handler[Handler executa<br/>200 / 201 / 204]
    err_401_missing[401<br/>'Token ausente']
    err_401_invalid[401<br/>'Token inválido']
    err_401_expired[401<br/>'Token expirado']
    err_403[403<br/>'Permissão insuficiente']

    request --> has_header
    has_header -->|não| err_401_missing
    has_header -->|sim| extract
    extract --> decode
    decode -->|TokenExpiredError| err_401_expired
    decode -->|InvalidTokenError| err_401_invalid
    decode -->|ok| sub_check
    sub_check -->|não| err_401_invalid
    sub_check -->|sim| scopes_required
    scopes_required -->|"não (apenas Bearer)"| handler
    scopes_required -->|"sim (ex: scopes=admin)"| scope_in_jwt
    scope_in_jwt -->|não| err_403
    scope_in_jwt -->|sim| handler

    classDef errClass fill:#f8cecc,stroke:#b85450,color:#000
    classDef okClass fill:#d5e8d4,stroke:#82b366,color:#000
    class err_401_missing,err_401_invalid,err_401_expired,err_403 errClass
    class handler okClass
```

---

## Referência de Endpoints

A **documentação interativa completa** (com schemas Pydantic, exemplos auto-gerados, descrição de cada campo e funcionalidade de "Try it out") está disponível no **Swagger UI** em `http://localhost:8080/docs` quando o app está rodando. As tabelas abaixo são um resumo rastreável para consulta rápida, listando todos os 13 endpoints expostos.

### Autenticação (`/auth/*`)

| Método | Rota | Descrição | Auth | Status esperados |
|---|---|---|---|---|
| `POST` | `/auth/login` | Autentica via OAuth2PasswordRequestForm e emite access + refresh tokens JWT | Pública | 200, 401 |
| `POST` | `/auth/token` | OAuth2 client_credentials: autentica um serviço (client_id/secret) e emite token com `principal_type=service` | client_id/secret | 200, 400, 401 |
| `POST` | `/auth/refresh` | Renova o access token usando o refresh token (no body) | Pública | 200, 401 |
| `POST` | `/auth/logout` | Revoga o refresh token informado no body | Bearer | 204, 401 |

### Usuários (`/users/*`)

| Método | Rota | Descrição | Auth | Status esperados |
|---|---|---|---|---|
| `POST` | `/users/register` | Cadastra um novo usuário (papel criado sempre como `PARTICIPANT`) | Pública | 201, 400, 409, 422 |
| `GET` | `/users/me` | Retorna os dados do usuário autenticado | Bearer | 200, 401, 404 |
| `PATCH` | `/users/me` | Atualiza parcialmente o perfil próprio | Bearer | 200, 401, 404, 409, 422 |
| `PUT` | `/users/me/password` | Troca a senha (exige a senha atual + valida força da nova) | Bearer | 204, 400, 401, 422 |
| `DELETE` | `/users/me` | Desativa a conta própria (soft delete; novos logins e refreshes falham com 401) | Bearer | 204, 401, 404 |

### Administração (`/admin/*`)

Todas as rotas administrativas exigem **Bearer token com scope `admin`** no payload do JWT. Token de usuário comum recebe **403**.

| Método | Rota | Descrição | Status esperados |
|---|---|---|---|
| `GET` | `/admin/ping` | Healthcheck do gate de admin (demonstração da US-13) | 200, 401, 403 |
| `GET` | `/admin/users` | Lista paginada de usuários (query params: `limit`, `cursor`) | 200, 400, 401, 403 |
| `GET` | `/admin/users/{user_id}` | Retorna dados de um usuário pelo ID | 200, 401, 403, 404 |
| `PATCH` | `/admin/users/{user_id}` | Atualiza o papel (`access_level`) e/ou `is_active` de outro usuário | 200, 400, 401, 403, 404, 422 |
| `DELETE` | `/admin/users/{user_id}` | Desativa um usuário (admin **não** pode desativar a si mesmo → 400) | 204, 400, 401, 403, 404 |

### Outros

| Método | Rota | Descrição | Auth | Status |
|---|---|---|---|---|
| `GET` | `/health` | Healthcheck básico do serviço | Pública | 200 |
| `GET` | `/.well-known/jwks.json` | Chave pública (JWKS) para validação dos JWTs RS256 por outros serviços | Pública | 200 |

### Exemplos de uso

Recomenda-se testar os endpoints interativamente pelo **Swagger UI** em `http://localhost:8080/docs`, que renderiza formulários e schemas auto-gerados a partir dos modelos Pydantic.

Convenções para usar o Swagger:

- **Endpoints protegidos** (marcados como `Bearer` na tabela): clique no botão **Authorize** 🔒 no topo da página antes de chamar. Você pode preencher email + senha no formulário OAuth2 (o Swagger faz o login implícito e captura o token automaticamente) ou colar um JWT diretamente no campo `Value` do esquema HTTPBearer.
- **Endpoints administrativos** (`/admin/*`): o JWT autorizado precisa carregar `"admin"` no array `scopes` do payload. Para obter um JWT admin localmente, faça login com o admin root criado pelo seed do lifespan (credenciais default: `admin@local.dev` / `Admin@123`).
- **Papéis** são um enum no código (`PARTICIPANT`/`MANAGER`/`ADMIN`) — não há mais UUIDs de catálogo. O `PATCH /admin/users/{id}` recebe o papel como string (ex.: `{"access_level": "ADMIN"}`).

Os exemplos abaixo mostram os corpos de request/response que o Swagger usa internamente, com notas sobre o passo a passo na UI.

#### Autenticação

##### `POST /auth/login`

No Swagger, expanda o endpoint → **Try it out**. O formulário OAuth2 aparece com os campos `username`, `password`, `scope`, `client_id` e `client_secret`. Preencha apenas:

- **username**: o **email** cadastrado (convenção do `OAuth2PasswordRequestForm` do FastAPI).
- **password**: a senha do usuário.

Os demais campos (`scope`, `client_id`, `client_secret`) podem ficar vazios — os scopes do JWT vêm do `access_level` do usuário no banco, não do formulário. Clique em **Execute**.

```json
// Response 200
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhY2RlMDcwZC04YzRjLTRmMGQtOWQ4YS0xNjI4NDNjMTAzMzMiLCJzY29wZXMiOlsidXNlciJdLCJleHAiOjE3NjI4NDc2MDB9.fake-signature",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhY2RlMDcwZC04YzRjLTRmMGQtOWQ4YS0xNjI4NDNjMTAzMzMiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2MzQ1MjQwMH0.fake-signature",
  "token_type": "bearer"
}
```

> **Atalho:** ao clicar no botão **Authorize** 🔒 no topo da página e preencher email/senha, o Swagger já chama `/auth/login` internamente e injeta o token automaticamente nos próximos requests — não é necessário testar este endpoint separadamente.

##### `POST /auth/refresh`

Endpoint público. **Try it out** → preencha `refresh_token` no body com o token recebido no login → **Execute**.

```json
// Request body
{
  "refresh_token": "eyJhbGci..."
}

// Response 200
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

> A renovação **não revoga** o refresh atual — ele continua válido até expirar (default 7 dias) ou ser invalidado via `POST /auth/logout`.

##### `POST /auth/logout`

Endpoint protegido. Clique em **Authorize** 🔒 antes para popular o header. Depois, **Try it out** → informe no body o `refresh_token` que deseja revogar → **Execute**.

```json
// Request body
{
  "refresh_token": "eyJhbGci..."
}
```

```
// Response 204 (sem body)
```

> Exige **ambos os tokens**: o access_token é enviado no header `Authorization` pelo Swagger (após o Authorize) e o refresh_token vai no body como alvo da revogação. Operação idempotente — revogar token já revogado também retorna 204.

#### Usuários

##### `POST /users/register`

Endpoint público. **Try it out** → preencha os campos no formulário JSON → **Execute**.

```json
// Request body
{
  "first_name": "Maria",
  "last_name": "Silva",
  "username": "maria.silva",
  "email": "maria@example.com",
  "password": "Xp7#kM2$vLq9!Rt"
}

// Response 201
{
  "id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
  "first_name": "Maria",
  "last_name": "Silva",
  "username": "maria.silva",
  "email": "maria@example.com",
  "access_level": "PARTICIPANT",
  "is_active": true,
  "created_at": "2026-04-11T10:30:00Z"
}
```

> Se o cliente enviar `access_level` no body, o campo é **silenciosamente ignorado** (US-27): o campo nem existe em `UserCreate` e o cadastro público sempre cria papel `PARTICIPANT`. Promoção a `MANAGER`/`ADMIN` é exclusiva via `PATCH /admin/users/{id}` (US-18).

##### `GET /users/me`

Endpoint protegido. Após **Authorize** 🔒 no topo da página, expanda o endpoint → **Try it out** → **Execute** (sem parâmetros adicionais).

```json
// Response 200
{
  "id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
  "first_name": "Maria",
  "last_name": "Silva",
  "username": "maria.silva",
  "email": "maria@example.com",
  "access_level": "PARTICIPANT",
  "is_active": true,
  "created_at": "2026-04-11T10:30:00Z"
}
```

> O `user_id` retornado vem do claim `sub` do JWT — não é necessário enviá-lo na URL.

##### `PATCH /users/me`

Endpoint protegido. Após **Authorize**, **Try it out** → informe no body apenas os campos a alterar (todos opcionais) → **Execute**.

```json
// Request body
{
  "first_name": "Maria Eduarda",
  "email": "maria.eduarda@example.com"
}

// Response 200 — retorna o perfil completo já atualizado
{
  "id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
  "first_name": "Maria Eduarda",
  "last_name": "Silva",
  "username": "maria.silva",
  "email": "maria.eduarda@example.com",
  "access_level": "PARTICIPANT",
  "is_active": true,
  "created_at": "2026-04-11T10:30:00Z"
}
```

> Erros: **422** se `email` ou `username` malformado; **409** se o novo `email`/`username` já estiver em uso por outro usuário.

##### `PUT /users/me/password`

Endpoint protegido. Após **Authorize**, **Try it out** → informe `current_password` e `new_password` → **Execute**.

```json
// Request body
{
  "current_password": "Xp7#kM2$vLq9!Rt",
  "new_password": "OutraSenha@2026"
}
```

```
// Response 204 (sem body)
```

> Erros comuns: **401** se `current_password` estiver incorreta (defesa em profundidade — token roubado não basta para trocar a senha); **400** se `new_password` for igual à atual; **422** se a nova senha não atender à regra de força (≥8 chars, maiúscula, minúscula, dígito, caractere especial).

##### `DELETE /users/me`

Endpoint protegido. Após **Authorize**, **Try it out** → **Execute** (sem parâmetros).

```
// Response 204 (sem body)
```

> **Soft delete:** marca `is_active=false` mas preserva o registro físico. A partir da desativação:
> - `POST /auth/login` com as mesmas credenciais retorna **401** (`AuthService.login` rejeita usuários inativos);
> - `POST /auth/refresh` com tokens emitidos antes da desativação retorna **401** "Refresh token revogado" (`AuthService.refresh` verifica `is_active` no `user_repository` antes de emitir novo access token).

#### Administração

Todos os endpoints abaixo exigem que o JWT autorizado tenha `"admin"` nos scopes. Use o admin root criado pelo seed do lifespan (`admin@local.dev` / `Admin@123`) no **Authorize** 🔒 antes de testar.

##### `GET /admin/ping`

Após **Authorize** com JWT admin, **Try it out** → **Execute**.

```json
// Response 200
{
  "user_id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
  "status": "ok"
}
```

> Endpoint de demonstração do gate `admin` (US-13). Token sem o scope retorna **403** com `detail: "Permissão insuficiente: requer 'admin'."`.

##### `GET /admin/users`

**Try it out** → preencha os query params `limit` (entre 1 e 100, default 20) e opcionalmente `cursor` para paginação → **Execute**.

```json
// Response 200
{
  "items": [
    {
      "id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
      "first_name": "Maria",
      "last_name": "Silva",
      "username": "maria.silva",
      "email": "maria@example.com",
      "access_level": "PARTICIPANT",
      "is_active": true,
      "created_at": "2026-04-11T10:30:00Z"
    }
  ],
  "next_cursor": "bd0babc3-bd93-443d-aefb-5193f5e1f08c"
}
```

> Paginação por **cursor opaco** (US-14): para buscar a próxima página, copie o valor de `next_cursor` da resposta anterior e cole no campo `cursor` do próximo **Try it out**. Quando `next_cursor` retorna `null`, é o fim da lista.

##### `GET /admin/users/{user_id}`

**Try it out** → preencha o path param `user_id` com o UUID do usuário desejado → **Execute**.

```json
// Response 200 (mesmo schema UserResponse de GET /users/me)
{
  "id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
  "first_name": "Maria",
  "last_name": "Silva",
  "username": "maria.silva",
  "email": "maria@example.com",
  "access_level": "PARTICIPANT",
  "is_active": true,
  "created_at": "2026-04-11T10:30:00Z"
}
```

##### `PATCH /admin/users/{user_id}`

**Try it out** → preencha `user_id` no path e os campos a atualizar no body (todos opcionais) → **Execute**.

```json
// Request body — exemplo de promoção a admin
{
  "access_level": "ADMIN"
}

// Response 200
{
  "id": "acde070d-8c4c-4f0d-9d8a-162843c10333",
  "access_level": "ADMIN",
  "is_active": true,
  "first_name": "Maria",
  "last_name": "Silva",
  "username": "maria.silva",
  "email": "maria@example.com",
  "created_at": "2026-04-11T10:30:00Z"
}
```

> Outro uso comum: desativar um usuário com `{"is_active": false}`. O usuário promovido a admin precisa fazer **login novo** para que o JWT carregue `scopes=["user","admin"]` — tokens antigos continuam com o scope anterior até expirarem.

##### `DELETE /admin/users/{user_id}`

**Try it out** → preencha `user_id` no path com o UUID do usuário-alvo → **Execute**.

```
// Response 204 (sem body)
```

> Admin **não pode desativar a si mesmo** — se `user_id == admin_id`, retorna **400** com `detail: "Admin não pode desativar a si mesmo."`. Esse guard previne lockout total do painel administrativo.

#### Outros

##### `GET /health`

Endpoint público sem autenticação. **Try it out** → **Execute**.

```json
// Response 200
{"status": "ok"}
```

> Útil para probes de liveness/readiness em orquestradores (Kubernetes, ECS).

---

## Testes

```bash
pytest                                        # todos os testes
pytest --cov=app --cov-report=term-missing    # com cobertura
pytest tests/test_auth_service.py -v          # arquivo específico
```

Os testes unitários utilizam **dubles de teste** (Stub, Mock, Spy, Fake, Dummy) para isolar os use cases dos adaptadores de infraestrutura, e aplicam técnicas como **partição de equivalência**, **análise de valor limite**, **transição de estado** e **cobertura de decisão** para atingir a meta de **>80% de cobertura**.

Para detalhes completos sobre a estratégia de testes, dubles utilizados, tabelas de casos de teste e exemplos de código, consulte o **[TESTING.md](TESTING.md)**.

---

## Linting e Tipagem

```bash
# Linter + formatter (Ruff)
ruff check .
ruff format .

# Verificação de tipos estáticos (mypy)
mypy app/
```

As regras do Ruff e as configurações do mypy estão definidas em `pyproject.toml`.

---

## Controle de Versões e CI/CD

O projeto adota **GitFlow** — branches `feat/us-XX` partem de `dev` e voltam via **Squash and Merge**; releases de `dev` para `main` usam **Merge Commit** para preservar histórico. Detalhes completos no [CONTRIBUTING.md](CONTRIBUTING.md). O pipeline automatizado usa **GitHub Actions** em duas configurações distintas.

### Organização do Backlog em Épicos

O backlog do projeto, mantido nas [Issues do GitHub](https://github.com/pucrs-csw-2026-1/0x_t1/issues), está estruturado em **5 épicos** que refletem deliberadamente as camadas e *concerns* da [Arquitetura Hexagonal](#arquitetura-hexagonal). Cada User Story carrega a label do seu épico, permitindo navegação e priorização por área no GitHub Projects.

| Épico | Descrição | Mapeia para | User Stories implementadas |
|---|---|---|---|
| **Domínio** | Camada pura com as regras que o resto do sistema respeita | `app/domain/` | US-01 (validação) · US-02 (mensagens de erro) |
| **Persistência** | Armazenamento seguro dos dados de usuários e das senhas | `app/ports/user_repository.py` + `app/adapters/dynamo_user_repository.py` + `app/adapters/bcrypt_password_hasher.py` | US-03 (UserRepository + DynamoDB) · US-04 (bcrypt) |
| **Autenticação** | Fluxo OAuth2 completo (emissão e gerenciamento de tokens) | `app/adapters/jwt_token_provider.py` + `app/application/auth_service.py` + `app/adapters/api/auth_router.py` | US-05 (JWT) · US-06 (login) · US-07 (refresh) · US-08 (logout) |
| **Usuários** | Endpoints de criação de conta e manipulação do próprio perfil | `app/application/user_service.py` + `app/adapters/api/user_router.py` (rotas `/users/*`) | US-09 (cadastro) · US-10 (consulta) · US-15 (atualização) · US-16 (senha) · US-17 (desativação) |
| **Autorização** | Proteção de rotas por autenticação e restrição por perfil | `app/adapters/api/dependencies.py` (`get_current_user`, `Security` scopes) + `app/adapters/api/admin_router.py` (rotas `/admin/*`) | US-11 (Bearer gate) · US-12 (scope per profile) · US-13/US-27 (papel enum + scopes cumulativos + descarte de auto-promoção) · US-14 (listing) · US-18 (admin CRUD) |

**Critério arquitetural por trás da divisão:** cada épico corresponde a uma camada ou *concern* isolável da arquitetura hexagonal, o que permite que uma feature branch (`feat/us-XX`) tenha escopo bem delimitado dentro de uma única camada. Isso reduz conflito de merge entre PRs paralelas (uma equipe pode trabalhar em Persistência enquanto outra mexe em Autenticação sem se tocarem) e simplifica revisão (o reviewer sabe a priori que tipo de mudança esperar).

> **Story-zero** (não numerada): configuração do ambiente de desenvolvimento com Terraform + LocalStack, entregue antes da US-01 como pré-requisito para todas as entregas subsequentes.

> **Backlog não implementado** (issues [#63-#69](https://github.com/pucrs-csw-2026-1/0x_t1/issues?q=is%3Aissue+US-19+OR+US-20+OR+US-21+OR+US-22+OR+US-23+OR+US-24+OR+US-25), fechadas como fora do escopo desta entrega): reset de senha por email (US-19), verificação de email (US-20), notificação de senha alterada (US-21), token exchange para headers internos assinados (US-22), migração do `SECRET_KEY` para AWS Secrets Manager (US-23), histórico de tentativas de login (US-24) e histórico de mudanças sensíveis em contas (US-25). Indicam direções prováveis de evolução pós-entrega.

### Pipeline CI (`dev`)

Executada em todo **push** e **pull request** para `dev`.

```
┌──────────┐     ┌────────────┐     ┌──────────────────────┐
│   Ruff   │     │   mypy     │     │                      │
│  (lint + │     │ (tipagem   │────►│   Pytest (testes +   │
│  format) │     │  estática) │     │   cobertura >= 80%)  │
└──────────┘     └────────────┘     └──────────────────────┘
      │                │                       │
      └────── rodam em paralelo ───────┘       │
                                        depende de ambos
```

| Job | O que faz |
|---|---|
| **Lint** | `ruff check .` + `ruff format --check .` |
| **Typecheck** | `mypy app/` |
| **Test** | `pytest --cov --cov-fail-under=80` (só roda se lint e typecheck passarem) |

### Pipeline CD (`main`)

Executada em todo **push** para `main` (após merge de `dev` ou `hotfix/*`).

```
┌──────────┐     ┌────────────┐     ┌──────────┐     ┌──────────────┐
│   Ruff   │     │   mypy     │     │  Pytest  │     │    Build     │
│  (lint)  │     │ (tipagem)  │────►│ (testes) │────►│ docker build │
└──────────┘     └────────────┘     └──────────┘     └──────────────┘
      │                │                  │                 │
      └─── paralelo ───┘                  │                 │
                                    depende de              │
                                    lint + typecheck   depende de test
```

| Job | O que faz |
|---|---|
| **Lint** | Mesmas verificações do CI |
| **Typecheck** | Mesmas verificações do CI |
| **Test** | Mesmas verificações do CI |
| **Build** | `docker build -f backend/Dockerfile backend/` — valida que a imagem da aplicação constrói sem erro. Tag: `auth-service:${{ github.sha }}` |

> O step de **deploy** (push ECR + deploy ECS) será adicionado quando houver infraestrutura AWS disponível. O job atual de build serve como gate de empacotamento — falha aqui bloqueia o release.

### Outros workflows de governance

Além de CI e CD, o repositório usa dois workflows utilitários que enforçam a política de branches:

#### `pr-gate.yml` — proteção da `main`

Roda em todo pull request com destino a `main`. **Bloqueia** PRs que não venham de `dev` ou de uma branch `hotfix/*`. É o que transforma a convenção GitFlow em regra automática — sem isso, era só convenção, e qualquer feature branch poderia tentar entrar direto na main.

```
PR aberto em main
       │
       ▼
 head_ref == 'dev'  OR  startsWith(head_ref, 'hotfix/')?
       │                                │
       ├── sim ──► permite o PR ────────┤
       │                                │
       └── não ──► falha com erro ─────┘
                  (mensagem orientando o autor)
```

#### `sync-dev.yml` — sincronização de `dev` pós-merge

Roda em todo push para `main` (ou seja, após cada release ou hotfix). Faz `git merge origin/main` em `dev` automaticamente e dá push. Garante que `dev` nunca fica atrás de `main` — crítico no fluxo de **hotfix**, onde o fix vai direto pra main e precisa ser propagado para todas as feature branches subsequentes que partirão de `dev`.

---

## FAQ e Troubleshooting

### FAQ — perguntas conceituais

#### Como obtenho um token admin localmente para testar endpoints administrativos?

O serviço cria automaticamente um **admin root** durante o startup do app quando `app_env=development` (default em `.env`). Credenciais: `admin@local.dev` / `Admin@123`. Faça login normal via `POST /auth/login` (ou pelo botão **Authorize** do Swagger) com essas credenciais — o JWT retornado terá os scopes cumulativos de ADMIN: `scopes=["participant", "manager", "admin"]`.

Para promover **outro** usuário a admin (caso queira testar com identidade diferente do seed), use `PATCH /admin/users/{user_id}` informando `{"access_level": "ADMIN"}`. Detalhe importante: o usuário promovido precisa fazer **login novo** — JWTs antigos não recebem o scope retroativamente.

#### Tentei me cadastrar com `access_level: "ADMIN"` no body. Por que voltei como `PARTICIPANT`?

É proteção deliberada (US-27). O campo `access_level` nem existe em `UserCreate`, então é silenciosamente ignorado; o cadastro público sempre cria papel `PARTICIPANT`. Promoção a `MANAGER`/`ADMIN` é privilégio exclusivo de quem já é admin, via `PATCH /admin/users/{user_id}`. Veja [Segurança — OAuth2 + JWT](#segurança--oauth2--jwt) para o racional.

#### Tentei trocar minha senha para `Pass1234` mas recebi 422. Qual é a regra de força?

Mínimo 8 caracteres, com pelo menos: 1 maiúscula, 1 minúscula, 1 dígito **e 1 caractere especial** (qualquer um de `!@#$%^&*(),.?":{}|<>`). `Pass1234` falha porque não tem caractere especial. Exemplos válidos: `Senha@2026`, `MyP@ssword1`, `Test#1234`. A regra está em `validate_raw_password` em [`backend/app/domain/user.py`](backend/app/domain/user.py).

#### Promovi um usuário a admin mas o JWT dele continua sem o scope "admin". Bug?

Não é bug — é design intencional. O JWT é **imutável após emissão**. Ao alterar `access_level` no banco, isso só afeta **logins futuros**. O usuário precisa autenticar novamente (`POST /auth/login`) para receber um JWT atualizado com os scopes cumulativos do novo papel (ex.: ADMIN → `scopes=["participant","manager","admin"]`). Tokens antigos continuam com o scope anterior até expirarem (default 30 min para access, 7 dias para refresh).

#### Desativei minha conta (`DELETE /users/me`). Meu refresh token continua funcionando?

Não. Tanto `POST /auth/login` quanto `POST /auth/refresh` rejeitam tentativas de usuários desativados:

- **Login:** `AuthService.login` checa `if not user.is_active: raise InvalidCredentialsError`, mapeado para **401 "Credenciais inválidas"** (mesmo detail de senha errada — anti-enumeração).
- **Refresh:** `AuthService.refresh` carrega o `user` pelo `sub` do JWT e checa `if user is None or not user.is_active: raise TokenRevokedError`, mapeado para **401 "Refresh token revogado"**.

**Nota de implementação:** o `revoke_all_by_user` chamado em `deactivate` continua sendo no-op para o `InMemoryRefreshTokenRepository` (o adapter de dev não rastreia tokens emitidos no login). O bloqueio do refresh é feito pela checagem de `is_active` no caminho do refresh — não pela revogação explícita por token. Em produção, um adapter persistente (Redis/DDB) que registre tokens no login permitiria revogação estrutural complementar.

#### Como verifico se um email já está cadastrado antes de tentar registrar?

A API **não expõe** um endpoint público de "verificar email" — defesa contra enumeração de contas. O cliente deve esperar o 409 do `POST /users/register` e tratar como "conta já existe". Apenas admins podem listar usuários via `GET /admin/users`.

#### Quais são os papéis (`access_level`) e como viram scopes?

O papel é um enum no código (`Role` em [`backend/app/domain/access_level.py`](backend/app/domain/access_level.py)): `PARTICIPANT`, `MANAGER` ou `ADMIN`. Não há mais UUIDs nem tabela de catálogo (removidos na US-27).

Os scopes do JWT são derivados do papel de forma **cumulativa**:

- `PARTICIPANT` → `["participant"]`
- `MANAGER` → `["participant", "manager"]`
- `ADMIN` → `["participant", "manager", "admin"]`

Assim, o gate de `/admin/*` (que exige o scope `admin`) é satisfeito apenas por ADMIN.

### Troubleshooting — problemas comuns

#### App não sobe: `FileNotFoundError` em `keys/dev_private.pem`

**Sintoma:** ao executar `uvicorn app.main:app --reload`, o app (ou o primeiro request) falha porque não encontra o arquivo de chave RS256.

**Causa:** os caminhos `RSA_PRIVATE_KEY_PATH`/`RSA_PUBLIC_KEY_PATH` são resolvidos relativos ao **current working directory**. Rodando fora de `backend/`, `keys/dev_private.pem` não é encontrado.

**Solução:** rode a partir de `backend/` (onde está `keys/`), ou ajuste os paths no `.env`. Em dev, o par versionado em [`backend/keys/`](backend/keys/) já existe; não é preciso gerar nada.

#### `pytest` falha por não achar `.env` ou as chaves

**Sintoma:** rodar `pytest backend/tests/` a partir da raiz resulta em erros de coleta (`.env` ou `keys/dev_*.pem` não encontrados).

**Causa:** tanto `pydantic-settings` quanto os paths das chaves são relativos ao **current working directory**.

**Solução:** entre em `backend/` antes de rodar:

```powershell
cd backend; pytest tests/
```

#### Lifespan log: `falhou ao seedar admin`

**Sintoma:** no startup do app, aparece no log:

```
[lifespan] falhou ao seedar admin: ...
```

**Causa:** o DynamoDB não estava acessível no startup (Ministack fora do ar ou tabela `user` ausente). A função `_seed_root_admin` em `app/main.py` registra o admin root e define seu papel como `ADMIN` — se a tabela `user` não existir, a operação falha e o erro aparece como warning (não derruba o startup).

**Solução:** garanta o Ministack de pé e a tabela provisionada:

```bash
cd terraform && docker compose up -d && terraform apply -auto-approve
```

E reiniciar o app. O `--reload` do uvicorn detecta o arquivo mas pode não disparar o lifespan novamente — `Ctrl+C` e re-execução são mais seguros.

#### Swagger retorna 401 mesmo com Authorize feito

**Sintoma:** depois de clicar em **Authorize** com email/senha válidos e ver o cadeado fechado, ainda recebo 401 nos endpoints protegidos.

**Causas possíveis:**

1. **Token expirou** (default 30min). Refaça o Authorize.
2. **JWT colado manualmente com prefixo `Bearer ` duplicado** (ex: `Bearer eyJhbGci...`). O Swagger adiciona o prefixo automaticamente — cole apenas o JWT cru.
3. **App reiniciado entre o Authorize e o request.** O `InMemoryRefreshTokenRepository` perde estado, e tokens revogados na sessão anterior voltam a "funcionar". Para sessões realmente persistentes, é preciso um backing store externo (Redis/DDB) — fora do escopo desta entrega.

#### `/admin/users` retorna 500 com `KeyError: 'email'` ou similar

**Sintoma:** listagem admin quebra com KeyError em algum campo do schema `User`.

**Causa:** existe um item no DynamoDB salvo com schema incompleto. Cenário típico: rodaram `aws dynamodb update-item` com placeholder não substituído (ex: `{"id":{"S":"<USER_ID>"}}` literal), criando um item órfão com `id=""` e sem demais campos.

**Solução:**

```bash
# Identifica items órfãos no DDB local
aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name user

# Deleta o item parcial (ajuste o id conforme aparece no scan)
aws --endpoint-url=http://localhost:4566 dynamodb delete-item \
  --table-name user --key '{"id":{"S":""}}'
```

#### Bruno: variáveis aparecem como `{{baseUrl}}` literal na URL

**Sintoma:** ao executar um request no Bruno, a URL aparece como `{{baseUrl}}/users/register` ao invés de `http://127.0.0.1:8000/users/register`.

**Causa:** o environment `Local` não está selecionado.

**Solução:** no canto superior direito do Bruno, clique no dropdown de environment e selecione **Local**. Detalhes em [`bruno/README.md`](bruno/README.md).

#### Bruno demo retorna 409 sempre que tento rodar `09_Demo_Completa/01`

**Sintoma:** ao re-rodar a collection, o request 01 (Register Demo User) sempre falha com 409.

**Causa:** o usuário `demo@svc.local` já foi cadastrado em uma execução anterior. A coleção não cria automaticamente users com nomes únicos.

**Solução:** zerar o estado do DynamoDB local:

```bash
cd terraform
docker compose down -v       # remove o volume com dados
docker compose up -d
terraform apply -auto-approve
```

Depois reinicie o app (`uvicorn app.main:app --reload`) — o seed admin sobe junto.

#### Login retorna 401 imediatamente após `DELETE /users/me`

**Sintoma:** desativei a conta e agora `POST /auth/login` com as mesmas credenciais retorna 401.

**Resposta:** Comportamento esperado, não bug. `AuthService.login` rejeita credenciais de usuários inativos (`is_active=false`), retornando 401 genérico (mesma resposta de senha errada) para não revelar que a conta existe mas está inativa.

Para "voltar" uma conta desativada, é preciso usar `PATCH /admin/users/{user_id}` com `{"is_active": true}` — operação restrita a admins.

#### `ruff check` reclama de imports não ordenados em `main.py`

**Sintoma:** após adicionar imports novos, `ruff check app/` reporta `I001 Import block is un-sorted or un-formatted`.

**Causa:** os imports após `load_dotenv()` precisam estar em ordem alfabética. A regra de `# noqa: E402` aceita "imports tardios" (após código), mas eles ainda devem seguir a ordem.

**Solução:**

```powershell
cd backend
ruff check --fix app/    # auto-fix
ruff format app/
```
