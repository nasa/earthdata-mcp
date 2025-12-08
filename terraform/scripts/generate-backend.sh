#!/bin/sh
# Creates the Terraform remote S3 backend configuration for the passed in
# environment. Optionally the AWS region may be passed in; it defaults to
# 'us-east-1'. This script should be run from the terraform directory.

set -euo pipefail

CMR_ENVIRONMENT="$1"
AWS_REGION="${2:-us-east-1}"

SCRIPT_NAME="$(basename "$0")"

usage() {
  printf "Usage: %s <CMR_ENVIRONMENT> [<AWS_REGION>]\n" "$SCRIPT_NAME"
}

# Validate argument count
if [ "$#" -ne 1 ] && [ "$#" -ne 2 ]; then
    usage
    exit 1
fi

# Core remote state config
cat > terraform_backend.tf << EOF
terraform {
  backend "s3" {
    bucket         = "tf-state-cmr-${CMR_ENVIRONMENT}"
    key            = "cmr-mcp-state-${CMR_ENVIRONMENT}"
    region         = "${AWS_REGION}"
  }
}
EOF
