#!/bin/bash
set -e

# Bamboo task: Deploy database stack (RDS PostgreSQL with pgvector)
#
# NOTE: This task should normally be DISABLED. Only enable for initial
#       deployment or when database infrastructure changes are needed.
# Expects earthdata-mcp-deployed-package.tgz artifact from build plan.
#
# Bamboo Variables:
# +---------------------------------+----------+--------------------------------+
# | Variable                        | Required | Default                        |
# +---------------------------------+----------+--------------------------------+
# | bamboo_ENVIRONMENT_NAME         | Yes      | -                              |
# | bamboo_VPC_TAG_NAME_FILTER      | Yes      | -                              |
# | bamboo_SUBNET_TAG_NAME_FILTER   | Yes      | -                              |
# | bamboo_AWS_ACCESS_KEY_ID        | Yes      | -                              |
# | bamboo_AWS_SECRET_ACCESS_KEY    | Yes      | -                              |
# | bamboo_AWS_DEFAULT_REGION       | No       | us-east-1                      |
# | bamboo_DB_ENGINE_VERSION        | No       | 17.4                           |
# | bamboo_DB_INSTANCE_CLASS        | No       | db.t3.medium                   |
# +---------------------------------+----------+--------------------------------+

# Set AWS credentials from Bamboo variables
export AWS_DEFAULT_REGION="${bamboo_AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${bamboo_AWS_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${bamboo_AWS_SECRET_ACCESS_KEY}"

# Extract deployment package
echo "Extracting deployment package..."
tar -xzf earthdata-mcp-deployed-package.tgz
cd terraform

ENVIRONMENT="${bamboo_ENVIRONMENT_NAME}"
AWS_REGION="${AWS_DEFAULT_REGION}"

# Export required terraform variables
export TF_VAR_environment_name="$ENVIRONMENT"
export TF_VAR_aws_region="$AWS_REGION"
export TF_VAR_vpc_tag_name_filter="${bamboo_VPC_TAG_NAME_FILTER}"
export TF_VAR_subnet_tag_name_filter="${bamboo_SUBNET_TAG_NAME_FILTER}"

# Export optional terraform variables if set
[ -n "$bamboo_DB_ENGINE_VERSION" ] && export TF_VAR_engine_version="$bamboo_DB_ENGINE_VERSION"
[ -n "$bamboo_DB_INSTANCE_CLASS" ] && export TF_VAR_instance_class="$bamboo_DB_INSTANCE_CLASS"

STACK_DIR="database"

echo ""
echo "Deploying database stack"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"

cd "$STACK_DIR"

# Initialize Terraform
terraform init -input=false -no-color -reconfigure \
  -backend-config="bucket=tf-state-cmr-${ENVIRONMENT}" \
  -backend-config="key=earthdata-mcp/database-${ENVIRONMENT}" \
  -backend-config="region=${AWS_REGION}"

# Deploy database
terraform apply -no-color -auto-approve

echo ""
echo "Database stack deployed successfully"
