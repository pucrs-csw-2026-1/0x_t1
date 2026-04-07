# Estrategia de Testes

Este documento descreve a estrategia de testes unitarios do projeto, incluindo os tipos de dubles de teste utilizados, as tecnicas de projeto de casos de teste e a meta de cobertura.

---

## Dubles de Teste (Test Doubles)

Os testes unitarios isolam a camada de aplicacao (use cases) substituindo os **ports de saida** por dubles. Cada tipo de duble tem um papel especifico:

| Duble | O que faz | Onde e usado no projeto |
|---|---|---|
| **Stub** | Retorna respostas pre-definidas, sem logica de verificacao | `UserRepository`: retorna um usuario fixo para simular busca no DynamoDB sem acessa-lo |
| **Mock** | Verifica que determinadas interacoes aconteceram (chamadas, argumentos) | `TokenProvider`: verifica que `generate_access_token` foi chamado com o `user_id` correto apos login |
| **Spy** | Registra as chamadas recebidas para inspecao posterior, sem alterar comportamento | `PasswordHasher`: registra quantas vezes `hash` foi invocado para garantir que o cadastro faz hash exatamente uma vez |
| **Fake** | Implementacao funcional simplificada, usada quando stubs seriam complexos demais | `FakeUserRepository`: dicionario em memoria que implementa `UserRepository` com `save`, `find_by_email` e `find_by_id` reais |
| **Dummy** | Objeto passado apenas para satisfazer assinatura, nunca e utilizado de fato | Roles vazias (`[]`) em testes que validam apenas autenticacao, sem verificar autorizacao |

### Exemplo — Stub + Mock no teste de login

```python
async def test_login_com_credenciais_validas(auth_service, stub_user_repo, mock_token_provider):
    # Stub: UserRepository retorna usuario pre-definido
    stub_user_repo.find_by_email.return_value = fake_user

    # Stub: PasswordHasher confirma senha valida
    stub_hasher.verify.return_value = True

    result = await auth_service.login("maria@example.com", "S3nh@Forte!")

    # Mock: verifica que o token foi gerado com o user_id correto
    mock_token_provider.generate_access_token.assert_called_once_with(
        user_id=fake_user.id,
        scopes=fake_user.roles,
    )
    assert result.access_token is not None
```

### Exemplo — Fake no teste de cadastro

```python
async def test_cadastro_persiste_usuario(user_service, fake_user_repo):
    # Fake: repositorio em memoria com comportamento real
    result = await user_service.register(
        name="Maria Silva",
        email="maria@example.com",
        password="S3nh@Forte!",
        roles=["user"],  # Dummy: roles nao sao o foco deste teste
    )

    # Verifica que o fake persistiu o usuario
    saved = await fake_user_repo.find_by_email("maria@example.com")
    assert saved is not None
    assert saved.name == "Maria Silva"
```

---

## Tecnicas de Teste

Os testes unitarios aplicam tecnicas sistematicas para garantir cobertura de **>80%** com casos relevantes.

### Particao de Equivalencia

Divide o dominio de entrada em **classes equivalentes** — valores dentro de uma mesma classe devem produzir o mesmo comportamento, bastando testar um representante por classe.

**Validacao de email:**

| Classe | Representante | Resultado esperado |
|---|---|---|
| Email valido simples | `maria@example.com` | Aceita |
| Email valido com subdominio | `maria@mail.example.com` | Aceita |
| Email sem `@` | `mariaexample.com` | Rejeita |
| Email sem dominio | `maria@` | Rejeita |
| Email sem usuario | `@example.com` | Rejeita |
| String vazia | `""` | Rejeita |

**Validacao de senha (minimo 8 chars, 1 maiuscula, 1 numero, 1 especial):**

| Classe | Representante | Resultado esperado |
|---|---|---|
| Senha valida completa | `S3nh@Forte!` | Aceita |
| Sem caractere especial | `S3nhaForte1` | Rejeita |
| Sem numero | `Senh@Forte!` | Rejeita |
| Sem maiuscula | `s3nh@forte!` | Rejeita |
| Abaixo do tamanho minimo | `S3n@F!` | Rejeita |

**Credenciais de login:**

| Classe | Resultado esperado |
|---|---|
| Email existente + senha correta | Retorna tokens |
| Email existente + senha incorreta | `InvalidCredentialsError` |
| Email inexistente + qualquer senha | `InvalidCredentialsError` |

### Analise de Valor Limite

Testa os **limites exatos** dos intervalos aceitos, onde erros off-by-one sao mais provaveis.

**Tamanho da senha (minimo = 8 caracteres):**

| Valor | Tamanho | Resultado esperado |
|---|---|---|
| `S3n@Fo!` | 7 (limite - 1) | Rejeita |
| `S3n@For!` | 8 (limite exato) | Aceita |
| `S3n@Fort!` | 9 (limite + 1) | Aceita |

**Expiracao do access token (padrao = 30 minutos):**

| Valor | Resultado esperado |
|---|---|
| Token com `exp` = agora - 1s | `TokenExpiredError` |
| Token com `exp` = agora | Limite — comportamento definido pela lib |
| Token com `exp` = agora + 1s | Aceita |

**Tamanho do nome (minimo = 1, maximo = 255):**

| Valor | Tamanho | Resultado esperado |
|---|---|---|
| `""` | 0 | Rejeita |
| `"M"` | 1 | Aceita |
| `"M" * 255` | 255 | Aceita |
| `"M" * 256` | 256 | Rejeita |

### Teste de Transicao de Estado

Valida o comportamento do sistema conforme o **estado muda** ao longo de um fluxo.

**Ciclo de vida do refresh token:**

```
               login()                 refresh()              logout()
[Inexistente] ────────► [Ativo] ──────────────────► [Ativo] ──────────► [Revogado]
                           │                                                │
                           │            refresh()                           │
                           └──────────────────────► [Ativo]                 │
                                                                            │
                                                      refresh() apos logout │
                                                    [Revogado] ────► ERRO   │
```

| Estado inicial | Acao | Estado final | Resultado |
|---|---|---|---|
| Inexistente | `login()` | Ativo | Gera access + refresh tokens |
| Ativo | `refresh()` | Ativo | Gera novo access token |
| Ativo | `logout()` | Revogado | Refresh token invalidado |
| Revogado | `refresh()` | Revogado | `TokenRevokedError` |
| Revogado | `logout()` | Revogado | Idempotente (sem erro) |

**Estado do usuario:**

| Estado inicial | Acao | Estado final | Resultado |
|---|---|---|---|
| Nao cadastrado | `register()` | Cadastrado | Cria usuario |
| Cadastrado | `register()` mesmo email | Cadastrado | `EmailAlreadyExistsError` |
| Cadastrado | `login()` | Autenticado | Retorna tokens |

### Cobertura de Decisao (Branch Coverage)

Garante que cada **branch** (`if/else`, `try/except`) seja exercitada ao menos uma vez. Exemplos de decisoes criticas no `AuthService.login()`:

```python
async def login(self, email: str, password: str) -> TokenPair:
    user = await self.user_repo.find_by_email(email)
    if user is None:                          # Branch 1: usuario nao encontrado
        raise InvalidCredentialsError()

    if not self.hasher.verify(password, user.hashed_password):  # Branch 2: senha incorreta
        raise InvalidCredentialsError()

    access = self.token_provider.generate_access_token(...)     # Branch 3: sucesso
    refresh = self.token_provider.generate_refresh_token(...)
    return TokenPair(access_token=access, refresh_token=refresh)
```

| Teste | Branch exercitado |
|---|---|
| Email inexistente | Branch 1 (`user is None` = True) |
| Senha incorreta | Branch 2 (`verify` = False) |
| Credenciais validas | Branch 3 (caminho feliz) |

Para atingir **100% de branch coverage** neste metodo, os 3 testes acima sao necessarios e suficientes.

### Teste de Excecao e Erro

Valida que o sistema **falha de forma controlada** em condicoes anormais.

| Cenario | Excecao esperada |
|---|---|
| JWT com assinatura adulterada | `InvalidTokenError` |
| JWT com payload sem `sub` (user_id) | `InvalidTokenError` |
| JWT assinado com chave diferente | `InvalidTokenError` |
| Refresh token ja revogado | `TokenRevokedError` |
| Cadastro com email duplicado | `EmailAlreadyExistsError` |
| Senha fora das regras | `WeakPasswordError` |

---

## Cobertura e Meta de >80%

A cobertura minima de **80%** na pipeline e atingida combinando as tecnicas acima em cada camada:

| Camada | O que testar | Tecnica principal |
|---|---|---|
| **Domain** (entities, value objects) | Validacao de Email, senha, regras de negocio | Particao de equivalencia + valor limite |
| **Application** (use cases) | Fluxos de login, cadastro, refresh, logout | Transicao de estado + cobertura de decisao |
| **Adapters** (token provider, hasher) | Geracao/validacao JWT, hashing bcrypt | Teste de excecao + valor limite (expiracao) |

---

## Estrutura de Testes

```
tests/
├── conftest.py                  # Fixtures globais e dubles reutilizaveis
├── test_auth_service.py         # Use case de autenticacao
├── test_user_service.py         # Use case de cadastro e consulta
├── test_domain.py               # Entidades e value objects (email, senha)
├── test_token_provider.py       # Geracao e validacao de JWT
└── test_password_hasher.py      # Hashing e verificacao bcrypt
```
