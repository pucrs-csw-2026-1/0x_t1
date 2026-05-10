# Estratégia de Testes

Este documento descreve a estratégia de testes unitários do projeto, incluindo os tipos de **dubles de teste** utilizados, as **técnicas de projeto de casos de teste** aplicadas e a **meta de cobertura** exigida pela pipeline.

---

## Dubles de Teste (Test Doubles)

Os testes unitários isolam as camadas de aplicação e domínio substituindo os **ports de saída** (interfaces ABC) por dubles. Cada tipo de duble tem um papel específico:

| Duble | O que faz | Onde é usado no projeto |
|---|---|---|
| **Stub** | Retorna respostas pré-definidas, sem lógica de verificação | `UserRepository` mockado: `find_by_email.return_value = valid_user` simula busca no DynamoDB sem acessá-lo |
| **Mock** | Verifica que determinadas interações aconteceram (chamadas, argumentos) | `TokenProvider` mockado com `create_autospec`: confirma que `generate_access_token` foi chamado com `user_id` e `scopes` corretos |
| **Spy** | Registra as chamadas recebidas para inspeção posterior, sem alterar comportamento | `PasswordHasher` espião: registra quantas vezes `hash()` foi invocado, garantindo que o cadastro hasheia exatamente uma vez |
| **Fake** | Implementação funcional simplificada, usada quando stubs seriam complexos demais | [`tests/fakes/user_repository.py`](backend/tests/fakes/user_repository.py): `FakeUserRepository` é um dicionário em memória com `save`, `find_by_id`, `find_by_email`, `find_by_username`, `find_all` (com paginação determinística) |
| **Dummy** | Objeto passado apenas para satisfazer assinatura, nunca é utilizado de fato | `access_level=[]` em testes que validam apenas autenticação, sem verificar autorização |

### Exemplo — Stub + Mock no teste de login

```python
def test_login_com_credenciais_validas(
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
    jwt_token_provider: JwtTokenProvider,
    valid_user: User,
    fake_access_level_repo: FakeAccessLevelRepository,
) -> None:
    # Stub: UserRepository retorna usuário pré-definido
    user_repository_mock.find_by_email.return_value = valid_user

    # Stub: PasswordHasher confirma senha válida
    password_hasher_mock.verify.return_value = True

    auth_service = AuthService(
        user_repository=user_repository_mock,
        password_hasher=password_hasher_mock,
        token_provider=jwt_token_provider,
        access_level_repo=fake_access_level_repo,
    )

    tokens = auth_service.login(email=valid_user.email.value, password="Senha@123")

    # Verifica que tokens foram emitidos
    assert "access_token" in tokens
    assert "refresh_token" in tokens
```

### Exemplo — Fake no teste de cadastro

```python
def test_cadastro_persiste_usuario(
    fake_user_repo: FakeUserRepository,
    fake_access_level_repo: FakeAccessLevelRepository,
) -> None:
    user_service = UserService(
        user_repo=fake_user_repo,
        access_level_repo=fake_access_level_repo,
    )

    user = user_service.register(
        first_name="Maria",
        last_name="Silva",
        username="maria.silva",
        email="maria@example.com",
        password="Xp7#kM2$vLq9!Rt",
    )

    # O fake persistiu de verdade — verificação real
    saved = fake_user_repo.find_by_email(user.email)
    assert saved is not None
    assert saved.username.value == "maria.silva"
    assert saved.access_level == [USER_UUID]  # cadastro público → sempre 'user'
```

---

## Técnicas de Teste

Os testes unitários aplicam técnicas sistemáticas para garantir cobertura de **>80%** com casos relevantes.

### Partição de Equivalência

Divide o domínio de entrada em **classes equivalentes** — valores dentro de uma mesma classe devem produzir o mesmo comportamento, bastando testar um representante por classe.

**Validação de email:**

| Classe | Representante | Resultado esperado |
|---|---|---|
| Email válido simples | `maria@example.com` | Aceita |
| Email válido com subdomínio | `maria@mail.example.com` | Aceita |
| Email sem `@` | `mariaexample.com` | Rejeita (`InvalidEmailError`) |
| Email sem domínio | `maria@` | Rejeita |
| Email sem usuário | `@example.com` | Rejeita |
| String vazia | `""` | Rejeita |

**Validação de senha** (≥8 chars + 1 maiúscula + 1 minúscula + 1 dígito + 1 caractere especial):

| Classe | Representante | Resultado esperado |
|---|---|---|
| Senha válida completa | `Senha@2026` | Aceita |
| Sem caractere especial | `Senha2026` | Rejeita (`WeakPasswordError`) |
| Sem número | `Senha@aaa` | Rejeita |
| Sem maiúscula | `senha@2026` | Rejeita |
| Sem minúscula | `SENHA@2026` | Rejeita |
| Abaixo do mínimo | `Sn@1` | Rejeita |

**Validação de username** (regex `[a-zA-Z0-9_.]{8,25}`):

| Classe | Representante | Resultado esperado |
|---|---|---|
| Username válido | `maria.silva` | Aceita |
| Caracteres inválidos | `maria-silva` (hífen) | Rejeita (`InvalidUsernameError`) |
| Espaço | `maria silva` | Rejeita |
| Muito curto (< 8) | `mari` | Rejeita |
| Muito longo (> 25) | `m` × 30 | Rejeita |

**Credenciais de login (US-06):**

| Classe | Resultado esperado |
|---|---|
| Email existente + senha correta | Retorna tokens |
| Email existente + senha incorreta | `InvalidCredentialsError` → 401 |
| Email inexistente + qualquer senha | `InvalidCredentialsError` → 401 (anti-enumeração) |
| Email malformado + qualquer senha | `InvalidCredentialsError` → 401 (não 400, mesma defesa) |
| Email de usuário inativo + senha correta | `InvalidCredentialsError` → 401 (`is_active=false` bloqueia) |

**`access_level` no cadastro público (US-13):**

| Classe | Resultado esperado |
|---|---|
| Body sem `access_level` | Cadastra com `[user_uuid]` |
| Body com `access_level=[user_uuid]` | Cadastra com `[user_uuid]` |
| Body com `access_level=[admin_uuid]` (tentativa de auto-promoção) | Cadastra com `[user_uuid]` — campo silenciosamente descartado |

### Análise de Valor Limite

Testa os **limites exatos** dos intervalos aceitos, onde erros off-by-one são mais prováveis.

**Tamanho da senha** (mínimo = 8 caracteres):

| Valor | Tamanho | Resultado esperado |
|---|---|---|
| `Sn@1Aa` | 6 (limite − 2) | Rejeita |
| `Sn@1Aab` | 7 (limite − 1) | Rejeita |
| `Sn@1Aabc` | 8 (limite exato) | Aceita |
| `Sn@1Aabcd` | 9 (limite + 1) | Aceita |

**Expiração do access token** (default = 30 minutos):

| Valor | Resultado esperado |
|---|---|
| Token com `exp` = agora − 1s | `TokenExpiredError` → 401 |
| Token com `exp` = agora | Limite — comportamento definido pela lib (jose rejeita) |
| Token com `exp` = agora + 1s | Aceita |

**Tamanho do nome** (mínimo = 1, máximo = 255):

| Valor | Tamanho | Resultado esperado |
|---|---|---|
| `""` | 0 | Rejeita (`InvalidNameError`) |
| `"M"` | 1 | Aceita |
| `"M" × 255` | 255 | Aceita |
| `"M" × 256` | 256 | Rejeita |

**Paginação em `GET /admin/users` (US-14)** (`limit ∈ [1, 100]`):

| `limit` | Resultado esperado |
|---|---|
| `0` | 422 (validado pelo Pydantic via `Query(ge=1)`) |
| `1` | Aceita |
| `100` | Aceita |
| `101` | 422 (`Query(le=100)`) |

### Teste de Transição de Estado

Valida o comportamento do sistema conforme o **estado muda** ao longo de um fluxo.

**Ciclo de vida do refresh token** (US-06, US-07, US-08, US-17):

```
              login()              refresh()              logout()
[Inexistente] ───────► [Ativo] ──────────────► [Ativo] ──────────► [Revogado]
                          │                                              │
                          │   refresh()                                  │
                          └─────────────► [Ativo]                        │
                          │                                              │
                          │   user deactivate (US-17)                    │
                          ├─────────────► [Bloqueado por is_active]      │
                          │                                              │
                          │                  refresh() pós-logout        │
                          └──────────────► [Revogado] ──────► ERRO ◄─────┘
```

| Estado inicial | Ação | Estado final | Resultado |
|---|---|---|---|
| Inexistente | `login()` | Ativo | Gera access + refresh tokens |
| Ativo | `refresh()` | Ativo | Gera novo access token |
| Ativo | `logout()` | Revogado | Refresh invalidado no `InMemoryRefreshTokenRepository` |
| Revogado | `refresh()` | Revogado | `TokenRevokedError` → 401 |
| Revogado | `logout()` | Revogado | Idempotente (sem erro) |
| Ativo (user inativo) | `refresh()` | — | `TokenRevokedError` → 401 (checagem de `is_active` em `AuthService.refresh`) |

**Estado da conta (US-09, US-17):**

| Estado inicial | Ação | Estado final | Resultado |
|---|---|---|---|
| Não cadastrado | `register()` | Cadastrado (`is_active=true`) | Cria usuário com `access_level=[user_uuid]` |
| Cadastrado | `register()` mesmo email | Cadastrado | `EmailAlreadyExistsError` → 409 |
| Cadastrado | `login()` | Autenticado | Retorna tokens |
| Cadastrado | `DELETE /users/me` | Desativado (`is_active=false`) | 204 + tentativas de login/refresh subsequentes falham com 401 |

**Estado de permissão (US-12, US-13, US-18):**

| Estado inicial (`access_level`) | Ação | Estado final | Resultado |
|---|---|---|---|
| `[user_uuid]` | `PATCH /admin/users/{id}` com `[user_uuid, admin_uuid]` | `[user_uuid, admin_uuid]` | 200 — promovido; JWT antigo continua com scope antigo |
| `[user_uuid, admin_uuid]` | Login novo | `[user_uuid, admin_uuid]` | JWT emitido com `scopes=["user", "admin"]` |
| `[admin_uuid]` (do `admin` autenticado) | `DELETE /admin/users/{admin_id}` no próprio | — | 400 — admin não pode desativar a si mesmo |

### Cobertura de Decisão (Branch Coverage)

Garante que cada **branch** (`if/else`, `try/except`) seja exercitada ao menos uma vez. Exemplo crítico — `AuthService.refresh()` após o patch que conecta `is_active` ao ciclo do refresh:

```python
def refresh(self, refresh_token: str) -> str:
    # Branch 1: token está no set de revogados (logout explícito)
    if self._refresh_repository.is_revoked(refresh_token):
        raise TokenRevokedError()

    payload = self._token_provider.decode_token(refresh_token)
    # Branch 2: payload tem flag "revoked"
    if payload.get("revoked") is True:
        raise TokenRevokedError()

    user_id = payload["sub"]
    user = self._user_repository.find_by_id(user_id)
    # Branch 3: usuário não existe ou está desativado
    if user is None or not user.is_active:
        raise TokenRevokedError()

    # Branch 4: caminho feliz
    return self._token_provider.generate_access_token(...)
```

| Teste | Branch exercitado |
|---|---|
| `test_refresh_token_com_revoked_flag_lanca_excecao` | Branch 1 ou 2 (revogação) |
| `test_refresh_de_usuario_inexistente_lanca_token_revogado` | Branch 3 (`user is None`) |
| `test_refresh_de_usuario_desativado_lanca_token_revogado` | Branch 3 (`not user.is_active`) |
| `test_refresh_token_valido_retorna_novo_access_token` | Branch 4 (caminho feliz) |
| `test_refresh_token_expirado_lanca_excecao` | Branch externo (`TokenExpiredError` em `decode_token`) |
| `test_refresh_token_invalido_lanca_excecao` | Branch externo (`InvalidTokenError` em `decode_token`) |

Para atingir **100% de branch coverage** neste método, os 6 testes acima são necessários e suficientes.

### Teste de Exceção e Erro

Valida que o sistema **falha de forma controlada** em condições anormais.

| Cenário | Exceção esperada | Mapeamento HTTP |
|---|---|---|
| JWT com assinatura adulterada | `InvalidTokenError` | 401 |
| JWT com payload sem `sub` | `InvalidTokenError` | 401 |
| JWT assinado com chave diferente | `InvalidTokenError` | 401 |
| Refresh token já revogado | `TokenRevokedError` | 401 |
| Refresh token de usuário desativado | `TokenRevokedError` | 401 |
| Cadastro com email duplicado | `EmailAlreadyExistsError` | 409 |
| Atualização com email já em uso | `EmailAlreadyExistsError` | 409 |
| Atualização com username já em uso | `UsernameAlreadyExistsError` | 409 |
| Senha fora das regras | `WeakPasswordError` | 400 (register) ou 422 (change password) |
| Troca de senha sem senha atual correta | `InvalidCredentialsError` | 401 |
| Troca para senha igual à atual | `SamePasswordError` | 400 |
| Catálogo `access_level` vazio no cadastro | `AccessLevelNotFoundError` | 500 |
| `PATCH /admin/users/{id}` com UUID de `access_level` inexistente | `AccessLevelNotFoundError` | 422 |
| Admin desativando a si mesmo | `ValueError` | 400 |
| Cursor de paginação inválido | `InvalidPaginationError` | 400 |

---

## Cobertura e Meta de >80%

A cobertura mínima de **80%** é validada na pipeline CI (`--cov-fail-under=80`). É atingida combinando as técnicas acima em cada camada:

| Camada | O que testar | Técnicas principais | Arquivo |
|---|---|---|---|
| **Domain** (`app/domain/`) | Validação de `Email`, `Username`, `HashedPassword`, força de senha, regras de nome | Partição de equivalência + valor limite | [`tests/test_domain.py`](backend/tests/test_domain.py) |
| **Application** (`app/application/`) | Fluxos de login, refresh, logout, cadastro, troca de senha, deactivate, CRUD admin | Transição de estado + cobertura de decisão | [`tests/test_auth_service.py`](backend/tests/test_auth_service.py), [`tests/test_user_service.py`](backend/tests/test_user_service.py) |
| **Adapters de saída** (`app/adapters/*`) | Geração/validação JWT, hashing bcrypt, persistência DynamoDB com `moto` | Teste de exceção + valor limite (expiração, paginação) | [`tests/test_token_provider.py`](backend/tests/test_token_provider.py), [`tests/test_password_hasher.py`](backend/tests/test_password_hasher.py), [`tests/test_user_repository.py`](backend/tests/test_user_repository.py) |
| **Adapters de entrada** (`app/adapters/api/`) | Rotas FastAPI, contratos de request/response, mapeamento de exceções → HTTP, autenticação Bearer | Cobertura de decisão (status codes) + integração com `get_current_user` | [`tests/test_auth_router.py`](backend/tests/test_auth_router.py), [`tests/test_user_router.py`](backend/tests/test_user_router.py), [`tests/test_admin_router.py`](backend/tests/test_admin_router.py), [`tests/test_dependencies.py`](backend/tests/test_dependencies.py) |
| **Auditoria de rotas** | Garantir que toda rota não-pública declare autenticação | Reflection sobre o router FastAPI | [`tests/test_route_auth_audit.py`](backend/tests/test_route_auth_audit.py) |
| **Sistema (E2E)** | Fluxo ponta-a-ponta `register → login → me → refresh → logout` | Transição de estado em todas as camadas | [`tests/test_system_auth_flow.py`](backend/tests/test_system_auth_flow.py) |

---

## Estrutura de Testes

```
backend/tests/
├── conftest.py                  # Fixtures globais (valid_user, ADMIN_UUID, USER_UUID, etc.)
├── fakes/                       # Test doubles in-memory dos ports
│   ├── user_repository.py       # FakeUserRepository (dict em memória + paginação)
│   ├── access_level_repository.py  # FakeAccessLevelRepository (catálogo fixo)
│   └── refresh_token_repository.py # FakeRefreshTokenRepository (set de revogados)
│
├── test_domain.py               # Value objects e regras de validação
├── test_auth_service.py         # Use case de autenticação (login, refresh, logout)
├── test_user_service.py         # Use case de usuário (cadastro, perfil, senha, deactivate, admin CRUD)
├── test_token_provider.py       # JwtTokenProvider (jose)
├── test_password_hasher.py      # BcryptPasswordHasher (passlib)
├── test_user_repository.py      # DynamoUserRepository com moto (mock AWS)
│
├── test_auth_router.py          # Rotas /auth/* (login, refresh, logout)
├── test_user_router.py          # Rotas /users/* (register, me, password, deactivate)
├── test_admin_router.py         # Rotas /admin/* (ping, list, get, patch, delete)
├── test_dependencies.py         # get_current_user, require_scope
├── test_route_auth_audit.py     # Auditoria automática de rotas com/sem proteção
│
└── test_system_auth_flow.py     # Fluxo E2E ponta-a-ponta (TestClient + moto)
```

**Total:** 13 arquivos de teste cobrindo ~144 casos, com cobertura mantida acima de 80% pela pipeline CI.
