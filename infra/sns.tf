# Tópico SNS de eventos de usuário (US-29).
#
# O Auth publica o evento `UserProfileChanged` neste tópico sempre que a
# demografia ou o papel (access_level) de um usuário é criado/alterado.
# Consumidores (ex.: o microsserviço Metrics) assinam via SQS para enriquecer
# suas métricas com a demografia do usuário. O fan-out por SNS mantém o Auth
# desacoplado de quem consome.
resource "aws_sns_topic" "user_events" {
  name = "user-events"
}

# Principais autorizados no tópico. Em PRODUÇÃO, aponte para os ARNs das roles
# IAM dos serviços — ex.: a task role do Auth como único publisher e a do
# Metrics como único subscriber. Em dev/Ministack, o default é a conta
# determinística do LocalStack (000000000000).
variable "topic_publisher_principals" {
  type        = list(string)
  default     = ["000000000000"]
  description = "Principais com permissão de PUBLICAR no tópico (só o Auth em prod)."
}

variable "topic_subscriber_principals" {
  type        = list(string)
  default     = ["000000000000"]
  description = "Principais com permissão de ASSINAR o tópico (só o Metrics em prod)."
}

# Topic policy estrita (allow-list): apenas os principais declarados podem
# publicar/assinar. Fecha o fan-out para consumidores não autorizados e impede
# que um publisher não confiável forje eventos `UserProfileChanged`.
#
# Nota: o payload já é minimizado (sem e-mail/nome/senha; só UUID + demografia),
# e o `access_level` do evento é data-plane no Metrics (não decide autorização).
# Esta policy é a barreira de transporte. O Ministack/LocalStack não força IAM por
# padrão, então em dev isto é "policy as code" (documenta a intenção); a aplicação
# efetiva ocorre na AWS.
resource "aws_sns_topic_policy" "user_events" {
  arn = aws_sns_topic.user_events.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowPublishFromAuthOnly"
        Effect    = "Allow"
        Principal = { AWS = var.topic_publisher_principals }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.user_events.arn
      },
      {
        Sid       = "AllowSubscribeFromMetricsOnly"
        Effect    = "Allow"
        Principal = { AWS = var.topic_subscriber_principals }
        Action    = ["SNS:Subscribe", "SNS:Receive"]
        Resource  = aws_sns_topic.user_events.arn
      },
    ]
  })
}

output "user_events_topic_arn" {
  value       = aws_sns_topic.user_events.arn
  description = "ARN do tópico SNS de eventos de usuário (UserProfileChanged)."
}
