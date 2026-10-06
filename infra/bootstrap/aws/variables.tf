variable "region" {
  type    = string
  default = "us-east-1"
}

variable "github_repo" {
  description = "GitHub repository (owner/name) allowed to assume the pipeline role."
  type        = string
  default     = "sharathKumar-1123/idea-board"
}

variable "create_oidc_provider" {
  description = "Set to false if the account already has the GitHub OIDC provider (only one is allowed per account)."
  type        = bool
  default     = true
}

variable "pipeline_policy_arn" {
  description = "Permissions for the pipeline role."
  type        = string
  default     = "arn:aws:iam::aws:policy/AdministratorAccess"
}
