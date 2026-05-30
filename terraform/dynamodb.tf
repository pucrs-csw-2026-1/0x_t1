# Criação da tabela DynamoDB de usuários, incluindo índices secundários globais
# para consultas eficientes por email e nome de usuário.
#
# Nota (US-27): o papel do usuário (access_level) deixou de ser uma referência
# a um catálogo e passou a ser um enum no código (PARTICIPANT/MANAGER/ADMIN),
# gravado como string no próprio registro do usuário. A antiga tabela de
# catálogo "access_level" foi removida.
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
