#!/bin/sh
# Creates the Terraform remote S3 backend configuration for the passed in
# environment. Optionally the AWS region may be passed in, it will otherwise
# default to 'us-east-1'. Bamboo should use this to ensure only one deployment runs
# at a time, all deployments share the same state, and the state is saved in
# S3. This script should be run from the terraform directory. 

CMR_ENVIRONMENT=$1
AWS_REGION=${2-us-east-1}

SCRIPT_NAME=$(basename $0)

function usage
{
  printf "Usage: $SCRIPT_NAME <CMR_ENVIRONMENT> [<AWS_REGION>]\n"
}

if [ "$#" -ne 1 ] && [ "$#" -ne 2 ]; then
    usage
    exit 1
fi

# Core remote state.
cat > terraform_backend.tf << EOF
terraform {
  backend "s3" {
    bucket         = "tf-state-cmr-${CMR_ENVIRONMENT}"
    key            = "cmr-mcp-state-${CMR_ENVIRONMENT}"
    region         = "${AWS_REGION}"
  }
}
EOF
