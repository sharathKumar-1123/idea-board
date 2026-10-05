# Cloud-neutral output contract. Every cloud environment (envs/<cloud>) exposes these same
# outputs, so the deploy pipeline and Helm chart never need cloud-specific logic.

output "cloud" {
  value = "aws"
}

output "region" {
  value = var.region
}

output "cluster_name" {
  value = module.cluster.cluster_name
}

output "kubeconfig_command" {
  description = "Command that writes kubectl credentials for this cluster."
  value       = "aws eks update-kubeconfig --name ${module.cluster.cluster_name} --region ${var.region}"
}

output "db_host" {
  value = module.database.host
}

output "db_port" {
  value = module.database.port
}

output "db_name" {
  value = module.database.name
}

output "db_username" {
  value = module.database.username
}

output "db_password" {
  value     = module.database.password
  sensitive = true
}

output "ai_health_check_policy_arn" {
  value = aws_iam_policy.ai_health_check.arn
}
