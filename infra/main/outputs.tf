output "application_url" {
  value = var.certificate_arn == "" ? "http://${aws_lb.app.dns_name}" : "https://${var.domain_name}"
}
output "load_balancer_dns" {
  value = aws_lb.app.dns_name
}
output "cluster_name" {
  value = aws_ecs_cluster.lab.name
}
output "service_name" {
  value = aws_ecs_service.app.name
}
output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}
output "dashboard_name" {
  value = aws_cloudwatch_dashboard.lab.dashboard_name
}
