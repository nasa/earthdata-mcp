#!/bin/bash
set -e

# Bamboo task: Deploy application stack (Lambdas, SQS, SNS subscription)
#
# This is the main deployment task that runs on every deploy.
# Expects earthdata-mcp-deployed-package.tgz artifact from build plan.
#
# Bamboo Variables:
# +---------------------------------+----------+--------------------------------+
# | Variable                        | Required | Default                        |
# +---------------------------------+----------+--------------------------------+
# | bamboo_ENVIRONMENT_NAME         | Yes      | -                              |
# | bamboo_VPC_TAG_NAME_FILTER      | Yes      | -                              |
# | bamboo_SUBNET_TAG_NAME_FILTER   | Yes      | -                              |
# | bamboo_CMR_SNS_TOPIC_NAME       | Yes      | -                              |
# | bamboo_deploy_version           | Yes      | -                              |
# | bamboo_AWS_ACCESS_KEY_ID        | Yes      | -                              |
# | bamboo_AWS_SECRET_ACCESS_KEY    | Yes      | -                              |
# | bamboo_AWS_DEFAULT_REGION       | No       | us-east-1                      |
# | bamboo_CMR_URL                  | No       | https://cmr.earthdata.nasa.gov |
# | bamboo_EMBEDDING_MODEL          | No       | amazon.titan-embed-text-v2:0   |
# | bamboo_BEDROCK_REGION           | No       | us-east-1                      |
# | bamboo_EMBEDDINGS_TABLE         | No       | concept_embeddings             |
# | bamboo_ASSOCIATIONS_TABLE       | No       | concept_associations           |
# | bamboo_LANGFUSE_HOST            | No       |                                |
# | bamboo_LANGFUSE_PUBLIC_KEY      | No       |                                |
# | bamboo_LANGFUSE_SECRET_KEY      | No       |                                |
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
IMAGE_TAG="${bamboo_deploy_version}"

# Export required terraform variables
export TF_VAR_environment_name="$ENVIRONMENT"
export TF_VAR_aws_region="$AWS_REGION"
export TF_VAR_vpc_tag_name_filter="${bamboo_VPC_TAG_NAME_FILTER}"
export TF_VAR_subnet_tag_name_filter="${bamboo_SUBNET_TAG_NAME_FILTER}"
export TF_VAR_image_tag="$IMAGE_TAG"
export TF_VAR_cmr_sns_topic_name="${bamboo_CMR_SNS_TOPIC_NAME}"

# Export optional terraform variables if set
[ -n "$bamboo_CMR_URL" ] && export TF_VAR_cmr_url="$bamboo_CMR_URL"
[ -n "$bamboo_EMBEDDING_MODEL" ] && export TF_VAR_embedding_model="$bamboo_EMBEDDING_MODEL"
[ -n "$bamboo_BEDROCK_REGION" ] && export TF_VAR_bedrock_region="$bamboo_BEDROCK_REGION"
[ -n "$bamboo_EMBEDDINGS_TABLE" ] && export TF_VAR_embeddings_table="$bamboo_EMBEDDINGS_TABLE"
[ -n "$bamboo_ASSOCIATIONS_TABLE" ] && export TF_VAR_associations_table="$bamboo_ASSOCIATIONS_TABLE"
[ -n "$bamboo_LANGFUSE_HOST" ] && export TF_VAR_langfuse_host="$bamboo_LANGFUSE_HOST"
[ -n "$bamboo_LANGFUSE_PUBLIC_KEY" ] && export TF_VAR_langfuse_public_key="$bamboo_LANGFUSE_PUBLIC_KEY"

# Store Langfuse secret in SSM SecureString if provided
if [ -n "$bamboo_LANGFUSE_SECRET_KEY" ]; then
    aws ssm put-parameter \
        --name "${ENVIRONMENT}-langfuse-secret-key" \
        --value "$bamboo_LANGFUSE_SECRET_KEY" \
        --type SecureString \
        --overwrite
fi

SCRIPTS_DIR="scripts"
STACK_DIR="application"

echo ""
echo "Deploying application stack"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "Image tag: $IMAGE_TAG"

cd "$STACK_DIR"

# Initialize Terraform
terraform init -input=false -no-color -reconfigure \
  -backend-config="bucket=tf-state-cmr-${ENVIRONMENT}" \
  -backend-config="key=earthdata-mcp/application-${ENVIRONMENT}" \
  -backend-config="region=${AWS_REGION}"

# Step 1: Create ECR repositories first
echo ""
echo "Creating ECR repositories..."
terraform apply -no-color -auto-approve \
  -target=aws_ecr_repository.ingest_lambda \
  -target=aws_ecr_repository.embedding_lambda \
  -target=aws_ecr_repository.bootstrap_lambda

# Step 2: Build and push Docker images
echo ""
echo "Building and pushing Lambda images..."
cd ..
for dockerfile in IngestLambdaDockerfile EmbeddingLambdaDockerfile BootstrapLambdaDockerfile; do
    echo ""
    echo ">>> Building $dockerfile"
    ./"$SCRIPTS_DIR"/docker-build.sh "$dockerfile" "$ENVIRONMENT" "$IMAGE_TAG"
done

# Step 3: Deploy everything else
echo ""
echo "Deploying Lambda functions and infrastructure..."
cd "$STACK_DIR"
terraform apply -no-color -auto-approve

echo ""
echo "Application stack deployed successfully"
