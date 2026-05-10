# Guia de Contribuição

Este documento define as regras de contribuição para o projeto **Auth Service**, seguindo o modelo **GitFlow**.

---

## GitFlow — Modelo de Branches

```
main  ←  dev  ←  feature/<nome>
   ↑
   └── hotfix/<nome>   (correção urgente direto na main)
```

### Branches permanentes

| Branch | Propósito |
|---|---|
| `main` | Código em produção. Recebe merges **apenas** vindos de `dev` ou `hotfix/*` após aprovação. |
| `dev` | Branch de integração contínua. Toda nova funcionalidade é integrada aqui antes de ir para `main`. |

### Branches temporárias

| Tipo | Convenção de nome | Origem | Destino |
|---|---|---|---|
| Funcionalidade | `feature/<descrição-curta>` | `dev` | `dev` |
| Correção urgente | `hotfix/<descrição-curta>` | `main` | `main` + `dev` |
| Release | `release/<versão>` | `dev` | `main` + `dev` |

---

## Fluxo de Trabalho

### 1. Atualize a branch `dev` local

```bash
git checkout dev
git pull origin dev
```

### 2. Crie sua branch de feature

```bash
git checkout -b feature/minha-funcionalidade
```

### 3. Desenvolva com commits atômicos e descritivos

```bash
git add <arquivos>
git commit -m "feat: adiciona endpoint de refresh token"
```

### 4. Atualize a branch com as últimas mudanças de `dev`

```bash
git fetch origin
git rebase origin/dev
```

### 5. Abra um Pull Request

Abra um PR de `feature/minha-funcionalidade` para `dev`.

---

## Regras para Pull Requests

- O PR deve ter uma descrição clara do que foi implementado e o motivo.
- É obrigatória a revisão de **pelo menos 1 membro** da equipe antes do merge.
- Todos os checks de CI (testes, linting e tipagem) devem passar.
- Use **Squash and Merge** ao integrar `feature` → `dev`.
- Use **Merge Commit** ao integrar `dev` → `main` (ou `hotfix/*` → `main`).
- Nunca faça commits diretos em `main` ou `dev`.
- PRs para `main` que não venham de `dev` ou `hotfix/*` são **automaticamente bloqueados** pelo workflow [`pr-gate.yml`](.github/workflows/pr-gate.yml).

---

## Convenção de Commits (Conventional Commits)

Todos os commits devem seguir o padrão [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>: <descrição curta>
```

| Tipo | Descrição |
|---|---|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Alterações apenas em documentação |
| `style` | Formatação, ponto e vírgula, etc. (sem mudança de comportamento) |
| `refactor` | Refatoração sem mudança de comportamento |
| `test` | Adição ou correção de testes |
| `chore` | Tarefas de manutenção (deps, CI, build) |

### Exemplos

```
feat: adiciona endpoint de refresh token
fix: corrige validação de email duplicado
docs: atualiza README com instruções de DynamoDB Local
test: adiciona testes unitários para AuthService
refactor: extrai lógica de hashing para PasswordHasher port
chore: atualiza dependências do pytest
```

---

## Estrutura de Código

O projeto segue **Arquitetura Hexagonal**. Ao contribuir, respeite a separação de camadas:

- **Domain** (`app/domain/`): entidades e value objects. Sem dependências externas.
- **Ports** (`app/ports/`): interfaces (ABCs). Sem implementação concreta.
- **Application** (`app/application/`): use cases. Dependem apenas de ports e domain.
- **Adapters** (`app/adapters/`): implementações concretas (DynamoDB, JWT, bcrypt, FastAPI routers).

> Regra de ouro: o domínio nunca importa adaptadores. Adaptadores importam ports.

---

## CI/CD

As pipelines de **GitHub Actions** rodam automaticamente:

- **`dev`** (CI — [`ci.yml`](.github/workflows/ci.yml)): Ruff lint/format, mypy e pytest com cobertura mínima de 80%.
- **`main`** (CD — [`cd.yml`](.github/workflows/cd.yml)): mesmos checks + build da imagem Docker via [`backend/Dockerfile`](backend/Dockerfile).
- **PRs para `main`** ([`pr-gate.yml`](.github/workflows/pr-gate.yml)): bloqueia automaticamente PRs que não venham de `dev` ou `hotfix/*`.
- **Pós-merge em `main`** ([`sync-dev.yml`](.github/workflows/sync-dev.yml)): sincroniza `dev` com `main` automaticamente.

O PR só pode ser mergeado se **todos os checks passarem**. Não tente fazer bypass dos checks.

---

## Checklist antes de abrir o PR

- [ ] Código segue a arquitetura hexagonal (sem imports cruzados entre camadas)
- [ ] Testes unitários para novos use cases e regras de domínio
- [ ] Aplicou técnicas de teste adequadas (partição de equivalência, valor limite, etc.) — ver [TESTING.md](TESTING.md)
- [ ] `ruff check .` e `ruff format .` passam sem erros
- [ ] `mypy app/` passa sem erros
- [ ] `pytest --cov-fail-under=80` passa sem falhas
- [ ] Schemas de entrada/saída utilizam Pydantic `BaseModel`
- [ ] Configurações utilizam `pydantic-settings` (`BaseSettings`)
- [ ] Pipeline CI passa no PR antes de solicitar revisão
