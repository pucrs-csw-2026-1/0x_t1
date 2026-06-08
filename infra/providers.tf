terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Endpoint do DynamoDB local (Ministack). No host, o default aponta para
# localhost:4566. Quando o Terraform roda dentro do Compose, o serviço de
# provisionamento sobrescreve via TF_VAR_dynamodb_endpoint=http://infra:4566
# (nome do serviço na rede do Compose).
variable "dynamodb_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  # O Ministack/LocalStack multiplexa todos os serviços no mesmo endpoint
  # (porta 4566), então o SNS reusa o valor de `dynamodb_endpoint`.
  endpoints {
    dynamodb = var.dynamodb_endpoint
    sns      = var.dynamodb_endpoint
  }
}