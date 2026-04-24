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

resource "aws_dynamodb_table" "access_level" {
  name         = "access_level"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}
