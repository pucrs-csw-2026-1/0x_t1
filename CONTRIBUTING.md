# Guia de Contribuicao

Este documento define as regras de contribuicao para o projeto **Auth Service**, seguindo o modelo **GitFlow**.

---

## GitFlow — Modelo de Branches

```
main  ←  dev  ←  feature/<nome>
```

### Branches permanentes

| Branch | Proposito |
|---|---|
| `main` | Codigo em producao. Recebe merges **apenas** vindos de `dev` apos aprovacao. |
| `dev` | Branch de integracao continua. Toda nova funcionalidade e integrada aqui antes de ir para `main`. |

### Branches temporarias

| Tipo | Convencao de nome | Origem | Destino |
|---|---|---|---|
| Funcionalidade | `feature/<descricao-curta>` | `dev` | `dev` |
| Correcao urgente | `hotfix/<descricao-curta>` | `main` | `main` + `dev` |
| Release | `release/<versao>` | `dev` | `main` + `dev` |

---

## Fluxo de Trabalho

### 1. Atualize a branch dev local

```bash
git checkout dev
git pull origin dev
```

### 2. Crie sua branch de feature

```bash
git checkout -b feature/minha-funcionalidade
```

### 3. Desenvolva com commits atomicos e descritivos

```bash
git add <arquivos>
git commit -m "feat: adiciona endpoint de refresh token"
```

### 4. Atualize a branch com as ultimas mudancas de dev

```bash
git fetch origin
git rebase origin/dev
```

### 5. Abra um Pull Request

Abra um PR de `feature/minha-funcionalidade` para `dev`.

---

## Regras para Pull Requests

- O PR deve ter uma descricao clara do que foi implementado e o motivo.
- E obrigatoria a revisao de **pelo menos 1 membro** da equipe antes do merge.
- Todos os checks de CI (testes, linting e tipagem) devem passar.
- Use **Squash and Merge** ao integrar `feature` -> `dev`.
- Use **Merge Commit** ao integrar `dev` -> `main`.
- Nunca faca commits diretos em `main` ou `dev`.

---

## Convencao de Commits (Conventional Commits)

Todos os commits devem seguir o padrao [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>: <descricao curta>
```

| Tipo | Descricao |
|---|---|
| `feat` | Nova funcionalidade |
| `fix` | Correcao de bug |
| `docs` | Alteracoes apenas em documentacao |
| `style` | Formatacao, ponto e virgula, etc. |
| `refactor` | Refatoracao sem mudanca de comportamento |
| `test` | Adicao ou correcao de testes |
| `chore` | Tarefas de manutencao (deps, CI, build) |

### Exemplos

```
feat: adiciona endpoint de refresh token
fix: corrige validacao de email duplicado
docs: atualiza README com instrucoes de DynamoDB Local
test: adiciona testes unitarios para AuthService
refactor: extrai logica de hashing para PasswordHasher port
chore: atualiza dependencias do pytest
```

---

## Estrutura de Codigo

O projeto segue **Arquitetura Hexagonal**. Ao contribuir, respeite a separacao de camadas:

- **Domain** (`app/domain/`): entidades e value objects. Sem dependencias externas.
- **Ports** (`app/ports/`): interfaces (ABCs). Sem implementacao concreta.
- **Application** (`app/application/`): use cases. Dependem apenas de ports e domain.
- **Adapters** (`app/adapters/`): implementacoes concretas (DynamoDB, JWT, bcrypt, FastAPI routers).

> Regra de ouro: o dominio nunca importa adaptadores. Adaptadores importam ports.

---

## CI/CD

As pipelines de **GitHub Actions** rodam automaticamente:

- **`dev`** (CI): Ruff lint/format, mypy e pytest com cobertura minima de 80%.
- **`main`** (CD): mesmos checks + build da imagem Docker.

O PR so pode ser mergeado se **todos os checks passarem**. Nao tente fazer bypass dos checks.

---

## Checklist antes de abrir o PR

- [ ] Codigo segue a arquitetura hexagonal (sem imports cruzados entre camadas)
- [ ] Testes unitarios para novos use cases e regras de dominio
- [ ] Aplicou tecnicas de teste adequadas (particao de equivalencia, valor limite, etc.)
- [ ] `ruff check .` e `ruff format .` passam sem erros
- [ ] `mypy app/` passa sem erros
- [ ] `pytest --cov-fail-under=80` passa sem falhas
- [ ] Schemas de entrada/saida utilizam Pydantic `BaseModel`
- [ ] Configuracoes utilizam `pydantic-settings` (`BaseSettings`)
- [ ] Pipeline CI passa no PR antes de solicitar revisao
