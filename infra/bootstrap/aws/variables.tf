variable "region" {
  type    = string
  default = "us-east-1"
}

variable "github_repo" {
  description = "GitHub repository (owner/name) allowed to assume the pipeline role."
  type        = string
  default     = "sharathKumar-1123/idea-board"
}

# Numeric IDs used in GitHub's immutable OIDC subject. Look them up with:
#   gh api repos/<owner>/<repo>/actions/oidc/customization/sub   (sub_claim_prefix)
variable "github_owner_id" {
  description = "Numeric GitHub user/org ID of the repository owner."
  type        = string
  default     = "66818338"
}

variable "github_repo_id" {
  description = "Numeric GitHub repository ID."
  type        = string
  default     = "1405865317"
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
