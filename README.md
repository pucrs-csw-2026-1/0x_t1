# Auth Service — API de Autenticacao e Autorizacao

Servico RESTful responsavel pelo cadastro de usuarios, autenticacao via **OAuth2**, emissao de tokens de acesso (JWT) e validacao de permissoes. Construido com **FastAPI**, **Pydantic v2** e **DynamoDB**, seguindo **Arquitetura Hexagonal** (Ports and Adapters).

> Trabalho da disciplina de **Construcao de Software** — PUCRS, 2026/1.

### Autores

- Carlos Eduardo B. Mascarello
- Lucas A. Brentano
- Victória C. Marques

---

## Funcionalidades

| Funcionalidade | Descricao |
|---|---|
| **Cadastro de usuarios** | Criacao de conta com nome, e-mail, senha (hash bcrypt) e perfil de permissoes |
| **Autenticacao OAuth2** | Fluxo OAuth2 Password Bearer com emissao de tokens JWT |
| **Emissao de tokens** | Access token e refresh token com expiracao configuravel |
| **Validacao de permissoes** | Middleware que valida token e escopos do usuario em rotas protegidas |

---

## Tech Stack

| Camada | Tecnologia |
|---|---|
| Framework web | [FastAPI](https://fastapi.tiangolo.com/) |
| Linguagem | Python 3.12+ |
| Validacao e schemas | [Pydantic v2](https://docs.pydantic.dev/latest/) |
| Configuracao | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Tipagem estatica | [mypy](https://mypy-lang.org/) |
| Linter / Formatter | [Ruff](https://docs.astral.sh/ruff/) |
| Testes | [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) + [httpx](https://www.python-httpx.org/) |
| Mock DynamoDB | [moto](https://docs.getmoto.org/en/latest/) |
| Banco de dados | [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) via [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) |
| Autenticacao | OAuth2 (FastAPI) + JWT ([python-jose](https://python-jose.readthedocs.io/)) + bcrypt ([passlib](https://passlib.readthedocs.io/)) |

---

## Arquitetura Hexagonal

O projeto segue a **Arquitetura Hexagonal** (Ports and Adapters), separando o dominio da infraestrutura e permitindo que adaptadores sejam substituidos sem afetar a logica de negocio.

```
  ┌───────────────────────┐
  │   adapters/api/       │  Driving Adapters (entrada)
  │   FastAPI Routers     │  auth_router, user_router, dependencies
  └───────────┬───────────┘
              │ chama
  ┌───────────▼───────────┐
  │   application/        │  Use Cases
  │   auth_service        │  Orquestra dominio + ports
  │   user_service        │
  └───────────┬───────────┘
              │ usa
  ┌───────────▼───────────┐
  │   domain/             │  Entidade User, value objects, excecoes
  │   (sem deps externas) │  Regras de negocio puras
  └───────────────────────┘
              │ depende de (ABC)
  ┌───────────▼───────────┐
  │   ports/              │  Interfaces de saida
  │   UserRepository      │  TokenProvider, PasswordHasher
  └───────────┬───────────┘
              │ implementado por
  ┌───────────▼───────────┐
  │   adapters/           │  Driven Adapters (saida)
  │   DynamoDB, JWT,      │  dynamo_user_repository, jwt_token_provider,
  │   Bcrypt              │  bcrypt_password_hasher
  └───────────────────────┘
```

### Ports e ABC (Abstract Base Class)

Os **ports** sao interfaces definidas como **ABC** (`abc.ABC` + `@abstractmethod`) — a forma nativa do Python de declarar contratos abstratos. Qualquer adapter que herde de um port e obrigado a implementar todos os metodos, caso contrario o Python lanca `TypeError` ao instanciar.

```python
from abc import ABC, abstractmethod

# Port (interface abstrata)
class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...

# Adapter (implementacao concreta)
class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return bcrypt.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.verify(password, hashed)
```

Isso garante o **Dependency Inversion Principle**: os use cases dependem da ABC `PasswordHasher`, nunca de `BcryptPasswordHasher` diretamente. Se amanha trocarmos bcrypt por argon2, basta criar um novo adapter — sem alterar nenhum use case.

### Padroes de Projeto Utilizados

| Padrao | Onde | Como funciona no projeto |
|---|---|---|
| **Repository** | `ports/user_repository.py` -> `adapters/dynamo_user_repository.py` | ABC define `save`, `find_by_email`, `find_by_id`. O adapter implementa via boto3/DynamoDB. Os use cases usam a interface, sem saber que o banco e DynamoDB |
| **Strategy** | `ports/password_hasher.py` -> `adapters/bcrypt_password_hasher.py` | ABC define `hash` e `verify`. O adapter implementa com bcrypt. Pode ser trocado por argon2 sem alterar use cases. Mesmo principio para `TokenProvider` (JWT hoje, pode ser opaco amanha) |
| **Dependency Injection** | `adapters/api/dependencies.py` + `container.py` | FastAPI `Depends()` injeta as implementacoes concretas nos routers. O `container.py` monta as dependencias (qual adapter satisfaz qual port) |
| **DTO (Data Transfer Object)** | `adapters/api/auth_router.py`, `user_router.py` | Schemas Pydantic (`UserCreate`, `UserResponse`, `TokenResponse`) desacoplam a entrada/saida HTTP das entidades de dominio |

---

## Estrutura do Projeto

```
auth-service/
├── app/
│   ├── main.py                          # Ponto de entrada FastAPI
│   ├── config.py                        # Settings via pydantic-settings (BaseSettings)
│   ├── container.py                     # Composicao e injecao de dependencias
│   │
│   ├── domain/                          # Camada de Dominio (sem deps externas)
│   │   ├── user.py                      # Entidade User + value objects (Email, HashedPassword)
│   │   └── exceptions.py               # Excecoes de dominio
│   │
│   ├── ports/                           # Portas de saida (interfaces ABC)
│   │   ├── user_repository.py           # Interface: UserRepository
│   │   ├── token_provider.py            # Interface: TokenProvider
│   │   └── password_hasher.py           # Interface: PasswordHasher
│   │
│   ├── application/                     # Camada de Aplicacao (Use Cases)
│   │   ├── auth_service.py              # Logica de autenticacao e tokens
│   │   └── user_service.py              # Logica de cadastro e consulta
│   │
│   └── adapters/                        # Adaptadores (infraestrutura)
│       ├── api/                         # Driving Adapters (FastAPI)
│       │   ├── auth_router.py           # Rotas OAuth2 + schemas de auth
│       │   ├── user_router.py           # Rotas de usuarios + schemas
│       │   └── dependencies.py          # OAuth2PasswordBearer, get_current_user
│       ├── dynamo_user_repository.py    # UserRepository -> DynamoDB (boto3)
│       ├── jwt_token_provider.py        # TokenProvider -> python-jose
│       └── bcrypt_password_hasher.py    # PasswordHasher -> passlib/bcrypt
│
├── tests/
│   ├── conftest.py                      # Fixtures globais e dubles reutilizaveis
│   ├── test_auth_service.py             # Testes do use case de autenticacao
│   ├── test_user_service.py             # Testes do use case de usuarios
│   ├── test_domain.py                   # Testes de entidades e value objects
│   ├── test_token_provider.py           # Testes de geracao/validacao JWT
│   └── test_password_hasher.py          # Testes de hashing bcrypt
│
├── .env.example                         # Exemplo de variaveis de ambiente
├── pyproject.toml                       # Dependencias, mypy e Ruff
├── requirements.txt                     # Dependencias de producao
├── requirements-dev.txt                 # Dependencias de desenvolvimento
├── CONTRIBUTING.md                      # Regras de contribuicao (GitFlow)
├── TESTING.md                           # Estrategia de testes unitarios
└── README.md
```

---

## Configuracao e Instalacao

### Pre-requisitos

- Python 3.12+
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configurado **ou** [DynamoDB Local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html) para desenvolvimento

### 1. Clone e entre no diretorio

```bash
git clone https://github.com/<org>/auth-service.git
cd auth-service
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

### 3. Instale as dependencias

```bash
pip install -r requirements.txt        # producao
pip install -r requirements-dev.txt    # ferramentas de dev/test
```

### 4. Configure as variaveis de ambiente

Copie `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

```dotenv
# .env.example
APP_ENV=development
SECRET_KEY=troque-por-uma-chave-secreta-forte
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

AWS_REGION=us-east-1
DYNAMODB_ENDPOINT_URL=http://localhost:8000   # apenas para DynamoDB Local
DYNAMODB_TABLE_USERS=auth_users
```

A configuracao e carregada via `pydantic-settings` (`BaseSettings`), com validacao automatica de tipos e valores:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    aws_region: str = "us-east-1"
    dynamodb_endpoint_url: str | None = None
    dynamodb_table_users: str = "auth_users"

    model_config = SettingsConfigDict(env_file=".env")
```

### 5. (Opcional) Suba o DynamoDB Local via Docker

```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
```

---

## Executando a Aplicacao

```bash
uvicorn app.main:app --reload
```

A documentacao interativa estara disponivel em:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

---

## Seguranca — OAuth2 + JWT

O servico implementa o fluxo **OAuth2 Password Bearer** nativo do FastAPI:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
```

- **Login** (`POST /auth/login`): recebe credenciais via `OAuth2PasswordRequestForm`, valida e retorna access + refresh tokens JWT.
- **Rotas protegidas**: utilizam `Depends(get_current_user)`, que extrai e valida o token Bearer automaticamente.
- **Escopos**: permissoes granulares via `Security(get_current_user, scopes=["admin"])`.

### Fluxo de autenticacao

```
Cliente                         Auth Service
  │                                  │
  ├── POST /auth/login ─────────────►│
  │   (email + password)             │
  │                                  ├── Valida credenciais (bcrypt)
  │                                  ├── Gera access_token (JWT)
  │                                  ├── Gera refresh_token (JWT)
  │◄──── 200 {access_token, ...} ────┤
  │                                  │
  ├── GET /users/me ────────────────►│
  │   Authorization: Bearer <token>  │
  │                                  ├── Valida JWT (assinatura + exp)
  │                                  ├── Extrai user_id e scopes
  │◄──── 200 {user data} ────────────┤
```

---

## Referencia de Endpoints

### Usuarios

| Metodo | Rota | Descricao | Autenticacao |
|---|---|---|---|
| `POST` | `/users/register` | Cadastra um novo usuario | Publica |
| `GET` | `/users/me` | Retorna os dados do usuario autenticado | Bearer token |

### Autenticacao (OAuth2)

| Metodo | Rota | Descricao | Autenticacao |
|---|---|---|---|
| `POST` | `/auth/login` | Autentica via OAuth2PasswordRequestForm e retorna tokens | Publica |
| `POST` | `/auth/refresh` | Renova o access token usando o refresh token | Publica (refresh token no body) |
| `POST` | `/auth/logout` | Invalida o refresh token | Bearer token |

#### Exemplo — Cadastro (`POST /users/register`)

```json
// Request body
{
  "name": "Maria Silva",
  "email": "maria@example.com",
  "password": "S3nh@Forte!",
  "roles": ["user"]
}

// Response 201
{
  "id": "uuid-gerado",
  "name": "Maria Silva",
  "email": "maria@example.com",
  "roles": ["user"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Exemplo — Login OAuth2 (`POST /auth/login`)

```
// Request: application/x-www-form-urlencoded (OAuth2PasswordRequestForm)
username=maria@example.com&password=S3nh@Forte!

// Response 200
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

---

## Testes

```bash
pytest                                        # todos os testes
pytest --cov=app --cov-report=term-missing    # com cobertura
pytest tests/test_auth_service.py -v          # arquivo especifico
```

Os testes unitarios utilizam **dubles de teste** (Stub, Mock, Spy, Fake, Dummy) para isolar os use cases dos adaptadores de infraestrutura, e aplicam tecnicas como **particao de equivalencia**, **analise de valor limite**, **transicao de estado** e **cobertura de decisao** para atingir a meta de **>80% de cobertura**.

Para detalhes completos sobre a estrategia de testes, dubles utilizados, tabelas de casos de teste e exemplos de codigo, consulte o **[TESTING.md](TESTING.md)**.

---

## Linting e Tipagem

```bash
# Linter + formatter (Ruff)
ruff check .
ruff format .

# Verificacao de tipos estaticos (mypy)
mypy app/
```

As regras do Ruff e as configuracoes do mypy estao definidas em `pyproject.toml`.

---

## CI/CD — Pipelines

O projeto utiliza **GitHub Actions** com duas pipelines separadas:

### Pipeline CI (`dev`)

Executada em todo **push** e **pull request** para `dev`.

```
┌──────────┐     ┌────────────┐     ┌──────────────────────┐
│   Ruff   │     │   mypy     │     │                      │
│  (lint + │     │ (tipagem   │────►│   Pytest (testes +   │
│  format) │     │  estatica) │     │   cobertura >= 80%)  │
└──────────┘     └────────────┘     └──────────────────────┘
      │                │                       │
      └────── rodam em paralelo ───────┘       │
                                        depende de ambos
```

| Job | O que faz |
|---|---|
| **Lint** | `ruff check .` + `ruff format --check .` |
| **Typecheck** | `mypy app/` |
| **Test** | `pytest --cov --cov-fail-under=80` (so roda se lint e typecheck passarem) |

### Pipeline CD (`main`)

Executada em todo **push** para `main` (apos merge de `dev`).

```
┌──────────┐     ┌────────────┐     ┌─────────┐     ┌─────────┐
│   Ruff   │     │   mypy     │     │  Pytest │     │  Build  │
│  (lint)  │     │ (tipagem)  │────►│ (testes)│────►│ (Docker)│
└──────────┘     └────────────┘     └─────────┘     └─────────┘
```

| Job | O que faz |
|---|---|
| **Lint** | Mesmas verificacoes do CI |
| **Typecheck** | Mesmas verificacoes do CI |
| **Test** | Mesmas verificacoes do CI |
| **Build** | Constroi a imagem Docker (`docker build`) |

> O step de deploy (push ECR + ECS) sera adicionado quando houver infraestrutura AWS disponivel.
