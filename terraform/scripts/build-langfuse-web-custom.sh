#!/bin/bash

#################################################################################
# Custom Langfuse Web Image Builder
# URL: https://langfuse.com/self-hosting/configuration/custom-base-path
#
# Purpose: Builds a custom Langfuse web container with a specific base path
#          and pushes it to AWS ECR for deployment with ECS.
#
# Description:
# - Clones the official Langfuse repository
# - Builds the web container with NEXT_PUBLIC_BASE_PATH build arg
# - Tags and pushes to your AWS ECR repository
# - Required when deploying Langfuse on a custom path (e.g., /langfuse)
#   instead of the root path
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - Docker installed and running
# - ECR repository already created (via terraform module)
#
# Usage: ./build-langfuse-web-custom.sh <ENVIRONMENT> [BASE_PATH] [AWS_REGION]
#
# Examples:
#   ./build-langfuse-web-custom.sh sit
#   ./build-langfuse-web-custom.sh sit /langfuse us-east-1
#   ./build-langfuse-web-custom.sh prod /custom/path us-west-2
#
#################################################################################

# Check for environment parameter
if [ $# -eq 0 ]; then
    echo "Usage: $0 <ENVIRONMENT> [BASE_PATH] [AWS_REGION]"
    echo "Example: $0 sit"
    echo "Example: $0 prod /langfuse us-east-1"
    exit 1
fi

# Parameters
ENVIRONMENT="$1"
BASE_PATH="${2:-/langfuse}"
AWS_REGION="${3:-us-east-1}"

# Build variables
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_NAME="${ENVIRONMENT}-langfuse-web"
TEMP_TAG="langfuse-web-custom-build"

echo "Building Langfuse web image with custom base path:"
echo "  Environment: $ENVIRONMENT"
echo "  Base Path: $BASE_PATH"
echo "  Region: $AWS_REGION"
echo "  ECR URI: $ECR_URI/$IMAGE_NAME:latest"

# Clone repo
echo "Cloning Langfuse repository..."
rm -rf langfuse || true
git clone https://github.com/langfuse/langfuse.git
cd langfuse
git checkout production

# Build image
echo "Building custom web image..."
docker build -t "$TEMP_TAG" \
  --platform=linux/amd64 \
  --build-arg TARGETPLATFORM="linux/amd64" \
  --build-arg NEXT_PUBLIC_BASE_PATH="$BASE_PATH" \
  -f ./web/Dockerfile .

# Authenticate to ECR
echo "Authenticating to ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_URI"

# Tag and push
echo "Tagging image for ECR..."
docker tag "$TEMP_TAG" "$ECR_URI/$IMAGE_NAME:latest"

echo "Pushing $IMAGE_NAME to ECR..."
docker push "$ECR_URI/$IMAGE_NAME:latest"

# Cleanup
echo "Cleaning up local images..."
docker rmi "$TEMP_TAG" || true
docker rmi "$ECR_URI/$IMAGE_NAME:latest" || true

echo "✅ Successfully pushed $ECR_URI/$IMAGE_NAME:latest"
