#!/usr/bin/env bash
# Creates the S3 bucket that stores Terraform state (run once per AWS account).
# Usage: scripts/bootstrap-state.sh [bucket-name]
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${1:-idea-board-tfstate-${ACCOUNT_ID}}"

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket $BUCKET already exists."
else
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
  echo "Created bucket $BUCKET."
fi

aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo
echo "State bucket ready. Set GitHub repo variable TF_STATE_BUCKET=$BUCKET"
echo "Local init: (cd infra/envs/aws && terraform init -backend-config=\"bucket=$BUCKET\" -backend-config=\"region=$REGION\")"
