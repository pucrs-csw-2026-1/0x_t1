# Banco de Dados - Auth Service

## Tecnologia

O serviço utiliza **Amazon DynamoDB** como banco de dados NoSQL. Para o ambiente de desenvolvimento, a stack AWS é emulada localmente com **Ministack**, executado via Docker Compose, e provisionada de forma declarativa com **[Terraform](https://www.terraform.io/)**. Como o DynamoDB não impõe regras de esquema, a validação dos dados é responsabilidade do backend em **FastAPI**.

### Stack local

| Componente | Função |
| --- | --- |
| **Ministack** | Container que emula os serviços AWS (neste serviço, apenas DynamoDB) na porta `4566` |
| **Terraform** | Provisiona a tabela `user` e seus índices secundários no Ministack |
| **AWS provider** | Aponta para o endpoint local (`http://localhost:4566`) com credenciais fictícias (`test`/`test`) |

## Configuração e Instalação

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- [Terraform](https://developer.hashicorp.com/terraform/downloads) `>= 1.5`

### 1. Clone e entre no diretório

```bash
git clone https://github.com/pucrs-csw-2026-1/0x_t1.git
cd 0x_t1/terraform
```

### 2. Suba o container do Ministack

Na pasta `terraform/`, suba o emulador AWS local:

```bash
docker compose up -d
```

O Ministack fica exposto em `http://localhost:4566`. Para parar, use `docker compose down`.

### 3. Provisione a tabela com Terraform

Ainda na pasta `terraform/`, inicialize os providers e aplique a infraestrutura:

```bash
terraform init
terraform apply
```

Isso cria a tabela `user` e seus índices secundários (`email-index`, `username-index`) dentro do Ministack.

### 4. (Opcional) Verifique a tabela

Com a [AWS CLI](https://docs.aws.amazon.com/cli/) instalada, é possível inspecionar o estado do DynamoDB local:

```bash
aws --endpoint-url=http://localhost:4566 dynamodb list-tables
```

### Encerrando

```bash
terraform destroy   # remove os recursos provisionados
docker compose down # encerra o container do Ministack
```

> O volume `./.ministack-data` guarda o estado do container entre reinicializações. Apague-o se quiser começar do zero.

## Modelagem do Banco de Dados

A modelagem foi projetada na aplicação **Hackolade**. Ela foi projetada para suportar autenticação, controle de acesso e gerenciamento de usuários com eficiência.

![Modelo do Banco de Dados](db_model.png)

### Por que DynamoDB?

A escolha do DynamoDB como banco NoSQL se dá pela simplicidade do modelo chave-valor, que atende bem aos padrões de acesso do serviço de autenticação — predominantemente consultas diretas por `id`. Combinado com **Ministack**, é possível rodar toda a stack AWS em container, sem depender de serviços externos durante o desenvolvimento e testes.

### Validação dos dados

Como o DynamoDB não impõe regras de esquema, toda a validação é responsabilidade do backend em **FastAPI**, que garante:

- Unicidade de `username` e `email`;
- Formato válido de e-mail e tamanhos mínimos/máximos de campos de texto;
- Senha com mínimo de 8 caracteres, contendo letras maiúsculas, minúsculas, números e caracteres especiais (validada antes do hash);
- Obrigatoriedade dos campos marcados como não nulos na modelagem;
- Validade do papel `user.access_level` contra o enum `Role` (PARTICIPANT/MANAGER/ADMIN).

### Remoção lógica

Os registros da tabela `user` não são removidos fisicamente do banco. Em vez disso, o campo `is_active` é marcado como `false`, preservando o histórico e evitando quebra de referências em outras partes do sistema.

## Tabelas e Dicionário de Dados

### Principais Tabelas

| Tabela | Partition Key | Descrição |
| --- | --- | --- |
| `user` | `id` (UUID) | Armazena usuários cadastrados no sistema |

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
| `access_level` | String (enum) | Papel único do usuário: `PARTICIPANT`, `MANAGER` ou `ADMIN` | `"PARTICIPANT"` |

### Papel de acesso (`access_level`)

O papel é um **enum no código** (`Role`), não um registro de banco. Os scopes
do JWT são derivados do papel de forma **cumulativa** (ADMIN ⊇ MANAGER ⊇
PARTICIPANT). Não há tabela de catálogo nem integridade referencial a manter —
a validade do valor é garantida pelo backend (Pydantic + domínio).
