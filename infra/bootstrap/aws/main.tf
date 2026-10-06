# One-time account bootstrap, applied from a laptop by a human admin (short-lived `aws login` session):
#   - S3 bucket for the main stack's Terraform state
#   - GitHub OIDC identity provider + IAM role the pipeline assumes (no long-lived access keys)
# This stack keeps its own small state locally (chicken-and-egg: it creates the remote state bucket).

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "idea-board"
      ManagedBy = "terraform-bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  state_bucket = "idea-board-tfstate-${data.aws_caller_identity.current.account_id}"
  oidc_url     = "token.actions.githubusercontent.com"
  oidc_arn = (
    var.create_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.oidc_url}"
  )
  # GitHub keeps the owner's original casing in the token's `sub` claim; IAM matching is case-sensitive.
  repo_variants = distinct([var.github_repo, lower(var.github_repo)])
}

# ---------- Terraform state bucket ----------

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------- GitHub Actions OIDC ----------

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url            = "https://${local.oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

resource "aws_iam_role" "github_actions" {
  name                 = "idea-board-github-actions"
  description          = "Assumed by GitHub Actions on ${var.github_repo} (main branch only) via OIDC"
  max_session_duration = 7200 # EKS creation + deploy can exceed the 1h default

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "${local.oidc_url}:aud" = "sts.amazonaws.com" }
        # Only workflows running from the main branch of this repository can assume the role.
        StringLike = { "${local.oidc_url}:sub" = [for r in local.repo_variants : "repo:${r}:ref:refs/heads/main"] }
      }
    }]
  })
}

# Provisioning VPC/EKS/RDS/IAM needs broad rights; the trust policy above is what limits *who* gets them.
resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = var.pipeline_policy_arn
}
