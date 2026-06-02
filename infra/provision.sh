#!/bin/sh
# Provisionamento one-shot da infraestrutura local via Terraform.
#
# Usado pelo serviço `provision` do docker-compose da raiz. Garante a tabela
# `user` no DynamoDB do Ministack, mas só roda o Terraform quando necessário:
#
#   - Se o estado já contém a infra provisionada (volume `tfstate`), sai sem
#     rodar `terraform apply` — atende ao requisito de "não reprovisionar a
#     infra caso ela já exista".
#   - Caso contrário, aguarda o endpoint do DynamoDB ficar de pé e aplica.
#
# Os arquivos .tf são montados em /infra (read-only); tudo que o Terraform
# escreve (plugins + state) fica no volume `tfstate` montado em /state, para
# não tocar nos arquivos versionados do host.
set -eu

INFRA_DIR=/infra
WORK_DIR=/state/work
STATE=/state/terraform.tfstate
ENDPOINT="${TF_VAR_dynamodb_endpoint:-http://infra:4566}"

# Fast-path: infra já provisionada → não roda Terraform.
if [ -f "$STATE" ] && grep -q 'aws_dynamodb_table' "$STATE"; then
  echo "[provision] infraestrutura já provisionada (state em $STATE); pulando Terraform."
  exit 0
fi

# Aguarda o Ministack responder antes de aplicar.
echo "[provision] aguardando DynamoDB em $ENDPOINT ..."
i=0
while [ "$i" -lt 60 ]; do
  if wget -q -O /dev/null "$ENDPOINT/_localstack/health" 2>/dev/null; then
    echo "[provision] Ministack pronto."
    break
  fi
  i=$((i + 1))
  sleep 2
done

# Copia a config .tf para um diretório gravável (o /infra é read-only).
mkdir -p "$WORK_DIR"
cp "$INFRA_DIR"/*.tf "$WORK_DIR"/
[ -f "$INFRA_DIR/.terraform.lock.hcl" ] && cp "$INFRA_DIR/.terraform.lock.hcl" "$WORK_DIR"/
cd "$WORK_DIR"

echo "[provision] provisionando infraestrutura (terraform init + apply)..."
terraform init -input=false
terraform apply -auto-approve -state="$STATE"
echo "[provision] infraestrutura provisionada."
