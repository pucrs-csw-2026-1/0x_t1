# Guia de Integração — Auth Service

Contrato para os demais microserviços do ecossistema (Metrics, Event, Check-in,
Registration, Certificate) **consumirem** os tokens emitidos pelo Auth Service.

O Auth assina JWTs em **RS256** (par de chaves) e publica a chave pública via
**JWKS**. Cada serviço valida os tokens **localmente, com a chave pública** — sem
compartilhar segredo e sem chamar o Auth a cada request.

> **Você (consumidor) NÃO cria nenhum par de chaves.** O par RS256 existe só no
> Auth. Para **validar** tokens, use apenas a **chave pública do JWKS** (é pública,
> não é credencial, e não há nada a gerar). O único segredo que um serviço precisa
> é o seu **`client_secret`** — usado para obter um token de serviço via
> client_credentials (§3) — e isso é uma **credencial de cliente, não uma chave
> RSA**. Gerar chaves próprias quebraria a validação (chave errada).

---

## 1. Conceitos

- **Algoritmo:** `RS256` (assimétrico). O Auth assina com a privada; os
  consumidores validam com a pública.
- **JWKS:** `GET /.well-known/jwks.json` expõe a(s) chave(s) pública(s). O header
  de cada token traz um `kid`; o consumidor casa o `kid` do token com a chave do
  JWKS.
- **`principal_type`** (claim presente em todo token):
  - `user` — pessoa autenticada via login (`POST /auth/login`).
  - `service` — máquina autenticada via client_credentials (`POST /auth/token`).

### Claims do token

| Claim | Tipo | Descrição |
|---|---|---|
| `sub` | string | id do usuário (token de pessoa) ou `client_id` (token de serviço) |
| `scopes` | string[] | permissões do token (ver §4) |
| `principal_type` | `"user"` \| `"service"` | origem do token |
| `exp` | número | expiração (epoch) |
| `email` | string | (apenas tokens de usuário, quando disponível) |

---

## 2. Validar um token (todo consumidor faz isto)

Passos:

1. Buscar o JWKS em `GET {AUTH_URL}/.well-known/jwks.json` e **cachear** (a chave é
   estável; refaça o fetch só em falha de `kid`).
2. Ler o `kid` do header do token e selecionar a chave correspondente no JWKS.
3. Validar **assinatura (RS256)** e **`exp`**.
4. Autorizar pela aplicação: checar `scopes` (e `principal_type`, se a rota é só
   para serviço ou só para pessoa).

Exemplo (Python, `python-jose`):

```python
import requests
from jose import jwt

JWKS = requests.get(f"{AUTH_URL}/.well-known/jwks.json").json()  # cachear!

def validate(token: str) -> dict:
    # jose seleciona a chave do JWKS pelo kid do header e valida RS256 + exp
    return jwt.decode(token, JWKS, algorithms=["RS256"])

claims = validate(bearer_token)
if "metrics:read" not in claims["scopes"]:
    raise PermissionError("scope insuficiente")
```

Qualquer linguagem serve — o que importa é: **JWKS por `kid` + RS256 + checagem de
`exp` e `scopes`**. Nunca aceite tokens `HS*` (algoritmo simétrico): só `RS256`.

---

## 3. Obter um token de serviço (máquina → máquina)

Quando um serviço precisa chamar outro (ex.: o Metrics lê dados de Event/Check-in/
Registration/Auth), ele autentica como **cliente de serviço** e usa o token
resultante como `Bearer` na chamada ao serviço-alvo.

```bash
curl -X POST "{AUTH_URL}/auth/token" \
  -d grant_type=client_credentials \
  -d client_id=metrics-service \
  -d client_secret=<SECRET>
# => { "access_token": "<jwt>", "token_type": "bearer" }   (principal_type=service)
```

- Respostas: `200` (ok) · `400` (`unsupported_grant_type`) · `401` (credenciais
  inválidas).
- **Sem refresh token** (padrão OAuth2 para client_credentials); ao expirar, peça
  outro.
- O `client_secret` **nunca** vai no repositório: dev usa `.env`; produção, um
  cofre de segredos (AWS Secrets Manager).

---

## 4. Scopes

### Tokens de usuário (papel cumulativo)

O papel do usuário (`access_level`) é um enum; os scopes são **cumulativos**:

| Papel | scopes no token |
|---|---|
| `PARTICIPANT` | `participant` |
| `MANAGER` | `participant`, `manager` |
| `ADMIN` | `participant`, `manager`, `admin` |

### Tokens de serviço

Cada cliente de serviço recebe os scopes concedidos a ele. **Convenção:**
`recurso:ação` (ex.: `event:read`, `checkin:read`, `registration:read`,
`certificate:read`, `user:read`).

> **Responsabilidade do provedor:** o Auth apenas *emite* o token com os scopes.
> Cabe a **cada serviço-alvo** validar o token (via JWKS) **e checar o scope**
> exigido na sua rota. O vocabulário de scopes precisa ser acordado entre os times.

---

## 5. Referência rápida dos endpoints do Auth

| Método | Rota | Uso na integração |
|---|---|---|
| `GET` | `/.well-known/jwks.json` | chave pública para validar tokens (público) |
| `POST` | `/auth/token` | obter token de serviço (client_credentials) |
| `POST` | `/auth/login` | login de pessoa (emite access + refresh) |
| `POST` | `/auth/refresh` | renovar access token de pessoa |
| `GET` | `/health` | healthcheck |

---

## 6. Ambiente / chaves

- **Dev:** par RS256 versionado em `backend/keys/` (dev-only) e cliente de serviço
  seedado por config (`SERVICE_CLIENT_*` / `SERVICE_CLIENTS`). Veja
  [`backend/.env.example`](backend/.env.example).
- **Produção:** chave privada e secrets de cliente vêm de um cofre de segredos
  (AWS Secrets Manager); a chave pública continua exposta no JWKS. Nada disso é
  commitado.

---

## 7. Exemplo fim-a-fim (Metrics)

1. Usuário chama o Metrics com `Authorization: Bearer <user_token>`.
2. Metrics valida o token via JWKS (§2) e checa `scopes`.
3. Para enriquecer com demografia, o caminho preferido é **assíncrono**: o Metrics
   consome o evento `UserProfileChanged` publicado pelo Auth (ver §8) e mantém um
   cache local. (Alternativa síncrona: obter um **token de serviço** (§3) e chamar
   `GET {AUTH_URL}/users/...` com scope `user:read`.)
4. Mesmo padrão para ler de Event / Check-in / Registration — cada um validando o
   token de serviço do Metrics via JWKS e checando o scope.

---

## 8. Eventos publicados (SNS)

Além da integração síncrona por JWT, o Auth **publica eventos de domínio** em um
tópico **SNS** para consumidores assíncronos (fan-out por SQS). Isso mantém o Auth
desacoplado: ele não conhece quem consome.

### `UserProfileChanged`

Publicado sempre que a **demografia** ou o **papel** (`access_level`) de um usuário
é criado/alterado. É um *fat event*: carrega os dados inline, então o consumidor
**não** precisa chamar o Auth de volta.

- **Tópico:** `user-events` (ARN configurável via `SNS_USER_EVENTS_TOPIC_ARN`).
- **Atributo de mensagem:** `event_type = "UserProfileChanged"`.
- **Disparado em:** cadastro (`register`), atualização de perfil com mudança
  demográfica (`update_profile`) e mudança de papel por admin (`admin_update`).

**Payload (corpo da mensagem, JSON):**

```json
{
  "event_type": "UserProfileChanged",
  "user_id": "<uuid>",
  "age": 27,
  "area": "Engenharia",
  "gender": "M",
  "city": "Porto Alegre",
  "access_level": "PARTICIPANT",
  "occurred_at": "2026-06-08T12:00:00Z"
}
```

| Campo | Tipo | Observação |
|---|---|---|
| `user_id` | string | id do usuário (= `sub` do token) |
| `age` | número \| null | `0–150`; `null` se não informado |
| `area` | string \| null | área de atuação |
| `gender` | `F`\|`M`\|`OUTRO`\|`NAO_INFORMADO` \| null | |
| `city` | string \| null | |
| `access_level` | `PARTICIPANT`\|`MANAGER`\|`ADMIN` | papel atual |
| `occurred_at` | string (ISO 8601 UTC) | momento da publicação |

> **Garantia de entrega:** a publicação é **best-effort** — uma falha de SNS é
> logada mas **não** quebra o cadastro/atualização. Consumidores devem tolerar
> eventos eventualmente perdidos (ex.: reconciliação periódica via `GET /users`).
