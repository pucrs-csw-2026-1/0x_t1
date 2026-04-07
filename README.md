# Auth Service — API de Autenticação e Autorização

Serviço RESTful responsável pelo cadastro de usuários, autenticação, emissão de tokens de acesso (JWT) e validação de permissões. Construído com **FastAPI** e **DynamoDB**, projetado para ser reutilizado por outros sistemas ou microsserviços.

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| **Cadastro de usuários** | Criação de conta com nome, e-mail, senha (hash bcrypt) e perfil de permissões |
| **Autenticação (login)** | Validação de credenciais e geração de token JWT |
| **Emissão de tokens** | Tokens de acesso (*access token*) e renovação (*refresh token*) com expiração configurável |
| **Validação de permissões** | Middleware que valida o token e os escopos do usuário em cada rota protegida |

---

## Tech Stack

| Camada | Tecnologia |
|---|---|
| Framework web | [FastAPI](https://fastapi.tiangolo.com/) |
| Linguagem | Python 3.12+ |
| Tipagem estática | [mypy](https://mypy-lang.org/) + anotações nativas do Python |
| Linter / Formatter | [Ruff](https://docs.astral.sh/ruff/) |
| Testes | [Pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) + [httpx](https://www.python-httpx.org/) |
| Banco de dados | [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) (via [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)) |
| Autenticação | JWT ([python-jose](https://python-jose.readthedocs.io/)) + bcrypt ([passlib](https://passlib.readthedocs.io/)) |
| Variáveis de ambiente | [python-dotenv](https://pypi.org/project/python-dotenv/) |

---

## Estrutura do Projeto

```
auth-service/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Ponto de entrada da aplicação FastAPI
│   ├── config.py                # Configurações e variáveis de ambiente
│   ├── dependencies.py          # Dependências compartilhadas (get_current_user, etc.)
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py              # Schemas Pydantic (UserCreate, UserResponse, Token…)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # Rotas de login e refresh de token
│   │   └── users.py             # Rotas de cadastro e gerenciamento de usuários
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py      # Lógica de autenticação e emissão de tokens
│   │   └── user_service.py      # Lógica de negócio de usuários
│   └── db/
│       ├── __init__.py
│       └── dynamo.py            # Cliente DynamoDB e helpers de acesso a dados
├── tests/
│   ├── conftest.py              # Fixtures compartilhadas (app de teste, usuário mock…)
│   ├── test_auth.py             # Testes de autenticação e tokens
│   └── test_users.py            # Testes de cadastro e validação de usuários
├── .env.example                 # Exemplo de variáveis de ambiente
├── pyproject.toml               # Dependências, mypy e configuração do Ruff
├── requirements.txt             # Dependências de produção
├── requirements-dev.txt         # Dependências de desenvolvimento e testes
└── README.md
```

---

## Configuração e Instalação

### Pré-requisitos

- Python 3.12+
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configurado **ou** [DynamoDB Local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html) para desenvolvimento

### 1. Clone e entre no diretório

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
SECRET_KEY=troque-por-uma-chave-secreta-forte
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

AWS_REGION=us-east-1
DYNAMODB_ENDPOINT_URL=http://localhost:8000   # apenas para DynamoDB Local
DYNAMODB_TABLE_USERS=auth_users
```

### 5. (Opcional) Suba o DynamoDB Local via Docker

```bash
docker run -d -p 8000:8000 amazon/dynamodb-local
```

---

## Executando a Aplicação

```bash
uvicorn app.main:app --reload
```

A documentação interativa estará disponível em:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

---

## Referência de Endpoints

### Usuários

| Método | Rota | Descrição | Autenticação |
|---|---|---|---|
| `POST` | `/users/register` | Cadastra um novo usuário | ❌ Pública |
| `GET` | `/users/me` | Retorna os dados do usuário autenticado | ✅ Bearer token |

### Autenticação

| Método | Rota | Descrição | Autenticação |
|---|---|---|---|
| `POST` | `/auth/login` | Autentica e retorna access + refresh tokens | ❌ Pública |
| `POST` | `/auth/refresh` | Renova o access token usando o refresh token | ❌ Pública (refresh token no body) |
| `POST` | `/auth/logout` | Invalida o refresh token | ✅ Bearer token |

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

#### Exemplo — Login (`POST /auth/login`)

```json
// Request body
{
  "email": "maria@example.com",
  "password": "S3nh@Forte!"
}

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
# Executar todos os testes
pytest

# Com cobertura de código
pytest --cov=app --cov-report=term-missing

# Apenas um arquivo específico
pytest tests/test_auth.py -v
```

Os testes utilizam um cliente HTTP assíncrono (`httpx.AsyncClient`) apontado para a aplicação FastAPI em memória, sem necessidade de uma instância real do DynamoDB (mocks via `unittest.mock` ou `moto`).

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

## Contribuição — GitFlow

Este projeto segue o modelo **GitFlow**. A hierarquia de branches é:

```
main  ←  dev  ←  feature/<nome>
```

### Branches permanentes

| Branch | Propósito |
|---|---|
| `main` | Código em produção. Recebe merges **apenas** vindos de `dev` após aprovação. |
| `dev` | Branch de integração contínua. Toda nova funcionalidade é integrada aqui antes de ir para `main`. |

### Branches temporárias

| Tipo | Convenção de nome | Origem | Destino |
|---|---|---|---|
| Funcionalidade | `feature/<descricao-curta>` | `dev` | `dev` |
| Correção urgente | `hotfix/<descricao-curta>` | `main` | `main` + `dev` |
| Release | `release/<versao>` | `dev` | `main` + `dev` |

### Fluxo de trabalho

```bash
# 1. Atualize dev local
git checkout dev
git pull origin dev

# 2. Crie sua branch de feature
git checkout -b feature/minha-funcionalidade

# 3. Desenvolva, faça commits atômicos e descritivos
git add .
git commit -m "feat: adiciona endpoint de refresh token"

# 4. Atualize a branch com as últimas mudanças de dev
git fetch origin
git rebase origin/dev

# 5. Abra um Pull Request: feature/minha-funcionalidade → dev
```

### Regras para Pull Requests

- O PR deve ter uma descrição clara do que foi implementado e o motivo.
- É obrigatória a revisão de **pelo menos 1 membro** da equipe antes do merge.
- Todos os checks de CI (testes, linting e tipagem) devem passar.
- Use **Squash and Merge** ao integrar `feature` → `dev`.
- Use **Merge Commit** ao integrar `dev` → `main`.
- Nunca faça commits diretos em `main` ou `dev`.

### Convenção de commits (Conventional Commits)

```
feat:     nova funcionalidade
fix:      correção de bug
docs:     alterações apenas em documentação
style:    formatação, ponto e vírgula, etc.
refactor: refatoração sem mudança de comportamento
test:     adição ou correção de testes
chore:    tarefas de manutenção (deps, CI, build)
```

---

## Licença

Distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
