output "state_bucket" {
  description = "Set as GitHub repo variable TF_STATE_BUCKET."
  value       = aws_s3_bucket.state.bucket
}

output "github_actions_role_arn" {
  description = "Set as GitHub repo variable AWS_ROLE_ARN."
  value       = aws_iam_role.github_actions.arn
}
