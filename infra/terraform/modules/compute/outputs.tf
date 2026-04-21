output "alb_dns_name" {
  description = "ALB DNS name — point your domain's CNAME here."
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB hosted zone ID (for Route 53 alias records)."
  value       = aws_lb.main.zone_id
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "ingestor_task_definition_arn" {
  value = aws_ecs_task_definition.ingestor.arn
}
