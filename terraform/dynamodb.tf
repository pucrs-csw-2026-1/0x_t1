# Criação de tabelas DynamoDB para armazenar informações de usuários e níveis de acesso, incluindo índices secundários globais para consultas eficientes por email e nome de usuário.
resource "aws_dynamodb_table" "user" {
  name         = "user"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "email"
    type = "S"
  }
  attribute {
    name = "username"
    type = "S"
  }

  global_secondary_index {
    hash_key        = "email"
    name            = "email-index"
    projection_type = "ALL"
  }
  global_secondary_index {
    hash_key        = "username"
    name            = "username-index"
    projection_type = "ALL"
  }
}

# Criação de tabela DynamoDB para armazenar níveis de acesso, utilizando UUIDs gerados a partir de um namespace e um nome específico para cada nível de acesso, garantindo identificadores únicos e consistentes.
resource "aws_dynamodb_table" "access_level" {
  name         = "access_level"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

locals {
    access_level_namespace = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    admin_id = uuidv5(local.access_level_namespace, "admin")
    user_id = uuidv5(local.access_level_namespace, "user")
  }

  resource "aws_dynamodb_table_item" "access_level_admin" {
    table_name = aws_dynamodb_table.access_level.name
    hash_key   = aws_dynamodb_table.access_level.hash_key
    item = jsonencode({
      id = { S = local.admin_id }
      title = { S = "admin" }
    })
  }

  resource "aws_dynamodb_table_item" "access_level_user" {
    table_name = aws_dynamodb_table.access_level.name
    hash_key   = aws_dynamodb_table.access_level.hash_key
    item = jsonencode({
      id = { S = local.user_id }
      title = { S = "user" }
    })
  }
