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

output "user_events_topic_arn" {
  value       = aws_sns_topic.user_events.arn
  description = "ARN do tópico SNS de eventos de usuário (UserProfileChanged)."
}
