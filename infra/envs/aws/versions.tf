terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Partial config: bucket and region are passed at init time, e.g.
  #   terraform init -backend-config="bucket=<state-bucket>" -backend-config="region=us-east-1"
  backend "s3" {
    key          = "idea-board/aws/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}
