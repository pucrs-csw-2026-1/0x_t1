# Banco de Dados - Auth Service

## Tecnologia

O serviço utiliza **Amazon DynamoDB** como banco de dados NoSQL. A instância é rodada local em container via Docker Compose. Como o DynamoDB não apresenta regras, a validação dos dados e informações serão feitos pelo backend em **FastAPI**.

## Configuração e Instalação

### Pré-requisitos

- [DynamoDB Local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html)

### 1. Clone e entre no diretório

```bash
git clone https://github.com/pucrs-csw-2026-1/0x_t1.git
cd db
```

### 2. Rode o arquivo Docker Compose

Na pasta `db/`, suba o container do DynamoDB Local:

```bash
docker compose up -d
```

O serviço fica exposto em `http://localhost:8000`. Para parar, use `docker compose down`.

## Modelagem do Banco de Dados

A modelagem foi projetada na aplicação **Hackolade**. Ela foi projetada para suportar autenticação, controle de acesso e gerenciamento de usuários com eficiência.

![Modelo do Banco de Dados](db_model.png)

### Por que DynamoDB?

A escolha do DynamoDB como banco NoSQL se dá pela simplicidade do modelo chave-valor, que atende bem aos padrões de acesso do serviço de autenticação — predominantemente consultas diretas por `id`. Além disso, o DynamoDB Local permite rodar toda a stack em container, sem depender de serviços externos durante o desenvolvimento e testes.

### Validação dos dados

Como o DynamoDB não impõe regras de esquema, toda a validação é responsabilidade do backend em **FastAPI**, que garante:

- Unicidade de `username` e `email`;
- Formato válido de e-mail e tamanhos mínimos/máximos de campos de texto;
- Senha com mínimo de 8 caracteres, contendo letras maiúsculas, minúsculas, números e caracteres especiais (validada antes do hash);
- Obrigatoriedade dos campos marcados como não nulos na modelagem;
- Integridade referencial entre `user.access_level` e a tabela `access_level`.

### Remoção lógica

Os registros da tabela `user` não são removidos fisicamente do banco. Em vez disso, o campo `is_active` é marcado como `false`, preservando o histórico e evitando quebra de referências em outras partes do sistema.

## Tabelas e Dicionário de Dados

### Principais Tabelas

| Tabela | Partition Key | Descrição |
| --- | --- | --- |
| `user` | `id` (UUID) | Armazena usuários cadastrados no sistema |
| `access_level` | `id` (UUID) | Define os níveis de acesso disponíveis no sistema |

### Dicionário de Dados

#### user

| Atributo | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `id` | String (UUID) | Atributo de identificação do usuário | `"acde070d-8c4c-4f0d-9d8a-162843c10333"` |
| `username` | String | Nome de usuário único para login | `"juca.bala_42"` |
| `password` | String | Hash bcrypt da senha do usuário | `"$2b$12$KIXxPfBpz5gQmJ4rL8xH2.eV3kN9tZwQ5cR7sD1aB6hG8jM0nP4qO"` |
| `first_name` | String | Nome social do usuário | `"Juca"` |
| `last_name` | String | Sobrenome do usuário | `"Bala"` |
| `email` | String | e-mail único do usuário | `"jucabala@email.com.br"` |
| `is_active` | Boolean | Verificador de usuário ativo para remoção lógica | `true` |
| `created_at` | String (date-time) | timestamp do momento de cadastro do usuário | `2001-09-11T12:30:00Z` |
| `updated_at` | String (date-time) | timestamp da última atualização do cadastro do usuário | `2026-04-11T14:30:00Z` |
| `access_level` | Lista [String (UUID)] | Lista de `access_level` com as UUID de autorização do usuário | `["uuid_0", "uuid_1"]` |

#### access_level

| Atributo | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `id` | String (UUID) | Atributo de identificação do nível de acesso | `"c32d8b45-92fe-44f6-8b61-42c2107dfe87"` |
| `title` | String | Nome simplificado do tipo de acesso | `"admin"` |

### Relações

| Origem | Destino | Cardinalidade | Campo | Tipo |
| --- | --- | --- | --- | --- |
| `user` | `access_level` | N:N | `user.access_level` | FK lógica (lista de UUIDs) |

A integridade referencial é garantida pelo backend em **FastAPI**, já que o DynamoDB não suporta chaves estrangeiras nativas. Antes de persistir um `user`, o serviço valida que todos os UUIDs em `access_level` existem na tabela `access_level`.