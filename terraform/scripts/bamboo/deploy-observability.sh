#!/bin/bash
set -e

# Bamboo task: Deploy observability stack (Langfuse)
#
# NOTE: This task should normally be DISABLED. Only enable for initial
#       deployment or when observability infrastructure changes are needed.
# Expects earthdata-mcp-deployed-package.tgz artifact from build plan.
#
# Bamboo Variables:
# +---------------------------------+----------+--------------------------------+
# | Variable                        | Required | Default                        |
# +---------------------------------+----------+--------------------------------+
# | bamboo_ENVIRONMENT_NAME         | Yes      | -                              |
# | bamboo_VPC_TAG_NAME_FILTER      | Yes      | -                              |
# | bamboo_SUBNET_TAG_NAME_FILTER   | Yes      | -                              |
# | bamboo_LOAD_BALANCER_NAME       | Yes      | (or bamboo_INTERNAL_LB)        |
# | bamboo_AWS_ACCESS_KEY_ID        | Yes      | -                              |
# | bamboo_AWS_SECRET_ACCESS_KEY    | Yes      | -                              |
# | bamboo_AWS_DEFAULT_REGION       | No       | us-east-1                      |
# | bamboo_LANGFUSE_BASE_PATH       | No       | /langfuse                      |
# | bamboo_LANGFUSE_WEB_CPU         | No       | 2048                           |
# | bamboo_LANGFUSE_WEB_MEMORY      | No       | 4096                           |
# | bamboo_LANGFUSE_WORKER_CPU      | No       | 2048                           |
# | bamboo_LANGFUSE_WORKER_MEMORY   | No       | 4096                           |
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
LANGFUSE_BASE_PATH="${bamboo_LANGFUSE_BASE_PATH:-/langfuse}"

# Export required terraform variables
export TF_VAR_environment_name="$ENVIRONMENT"
export TF_VAR_aws_region="$AWS_REGION"
export TF_VAR_vpc_tag_name_filter="${bamboo_VPC_TAG_NAME_FILTER}"
export TF_VAR_subnet_tag_name_filter="${bamboo_SUBNET_TAG_NAME_FILTER}"
export TF_VAR_load_balancer_name="${bamboo_LOAD_BALANCER_NAME:-${bamboo_INTERNAL_LB}}"
export TF_VAR_base_path="$LANGFUSE_BASE_PATH"

# Export optional terraform variables if set
[ -n "$bamboo_LANGFUSE_WEB_CPU" ] && export TF_VAR_web_cpu="$bamboo_LANGFUSE_WEB_CPU"
[ -n "$bamboo_LANGFUSE_WEB_MEMORY" ] && export TF_VAR_web_memory="$bamboo_LANGFUSE_WEB_MEMORY"
[ -n "$bamboo_LANGFUSE_WORKER_CPU" ] && export TF_VAR_worker_cpu="$bamboo_LANGFUSE_WORKER_CPU"
[ -n "$bamboo_LANGFUSE_WORKER_MEMORY" ] && export TF_VAR_worker_memory="$bamboo_LANGFUSE_WORKER_MEMORY"

SCRIPTS_DIR="scripts"
STACK_DIR="observability"

echo ""
echo "Deploying observability stack"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "Langfuse base path: $LANGFUSE_BASE_PATH"

cd "$STACK_DIR"

# Initialize Terraform
terraform init -input=false -no-color -reconfigure \
  -backend-config="bucket=tf-state-cmr-${ENVIRONMENT}" \
  -backend-config="key=earthdata-mcp/observability-${ENVIRONMENT}" \
  -backend-config="region=${AWS_REGION}"

# Step 1: Create ECR repositories first
echo ""
echo "Creating ECR repositories..."
terraform apply -no-color -auto-approve \
  -target=module.langfuse.aws_ecr_repository.langfuse_web \
  -target=module.langfuse.aws_ecr_repository.langfuse_worker

# Step 2: Build and push Langfuse images
echo ""
echo "Building and pushing Langfuse images..."
cd ..

echo ""
echo ">>> Building Langfuse web"
./"$SCRIPTS_DIR"/build-langfuse-web-custom.sh "$ENVIRONMENT" "$LANGFUSE_BASE_PATH" "$AWS_REGION"

echo ""
echo ">>> Building Langfuse worker"
./"$SCRIPTS_DIR"/build-langfuse-worker.sh "$ENVIRONMENT" latest "$AWS_REGION"

# Step 3: Deploy everything else
echo ""
echo "Deploying Langfuse infrastructure..."
cd "$STACK_DIR"
terraform apply -no-color -auto-approve

echo ""
echo "Observability stack deployed successfully"
