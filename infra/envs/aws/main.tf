provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

locals {
  tags = {
    Project     = var.name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "network" {
  source = "../../modules/aws/network"

  name               = var.name
  cidr               = var.vpc_cidr
  single_nat_gateway = var.single_nat_gateway
}

module "cluster" {
  source = "../../modules/aws/cluster"

  name                 = var.name
  kubernetes_version   = var.kubernetes_version
  admin_principal_arns = var.cluster_admin_arns
  vpc_id               = module.network.vpc_id
  subnet_ids           = module.network.private_subnet_ids
  node_instance_type   = var.node_instance_type
  node_min_size        = var.node_min_size
  node_max_size        = var.node_max_size
  node_desired_size    = var.node_desired_size
}

module "database" {
  source = "../../modules/aws/database"

  name                       = var.name
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  allowed_security_group_ids = [module.cluster.node_security_group_id]
  instance_class             = var.db_instance_class
  multi_az                   = var.db_multi_az
  deletion_protection        = var.db_deletion_protection
}

# Least-privilege policy for the AI health check. Attach it to whatever identity runs the
# pipeline (e.g. a GitHub OIDC role) instead of granting broad admin rights.
resource "aws_iam_policy" "ai_health_check" {
  name        = "${var.name}-ai-health-check"
  description = "Allows the deployment pipeline to call Amazon Bedrock models for health analysis"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel"] # also covers the Converse API
      Resource = "*"
    }]
  })
}
