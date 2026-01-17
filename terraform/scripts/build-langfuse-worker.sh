#!/bin/bash

#################################################################################
# Langfuse Worker Image Builder
#
# Purpose: Pulls the official Langfuse worker image and pushes it to AWS ECR
#          for deployment with ECS.
#
# Description:
# - Pulls the prebuilt langfuse/langfuse-worker image
# - Tags and pushes to your AWS ECR repository
# - No custom build needed for worker (unlike web container)
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - Docker installed and running
# - ECR repository already created (via terraform module)
#
# Usage: ./build-langfuse-worker.sh <ENVIRONMENT> [WORKER_VERSION] [AWS_REGION]
#
# Examples:
#   ./build-langfuse-worker.sh sit
#   ./build-langfuse-worker.sh sit latest us-east-1
#   ./build-langfuse-worker.sh prod 3.135.1
#
#################################################################################

# Check if environment is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <ENVIRONMENT> [WORKER_VERSION] [AWS_REGION]"
    echo "Example: $0 sit"
    echo "Example: $0 prod 3.135.1 us-east-1"
    exit 1
fi

# Parameters
ENVIRONMENT=$1
WORKER_VERSION=${2:-"latest"}  # Default to latest
AWS_REGION=${3:-"us-east-1"}   # Default region

# Get AWS Account ID
ACCOUNT=$(aws sts get-caller-identity --query "[Account][0]" --output text)
ECR_URI=$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
IMAGE_NAME="$ENVIRONMENT-langfuse-worker"

echo "Building Langfuse worker image:"
echo "  Environment: $ENVIRONMENT"
echo "  Version: $WORKER_VERSION"
echo "  Region: $AWS_REGION"

# Pull the official prebuilt worker image
echo "Pulling prebuilt worker image..."
docker pull --platform linux/amd64 langfuse/langfuse-worker:$WORKER_VERSION

# Tag for ECR
echo "Tagging image..."
docker tag langfuse/langfuse-worker:$WORKER_VERSION $ECR_URI/$IMAGE_NAME:latest

# Authenticate to ECR
echo "Authenticating to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_URI

# Push to ECR
echo "Pushing $IMAGE_NAME to ECR..."
docker push $ECR_URI/$IMAGE_NAME:latest

echo "✅ Successfully pushed $ECR_URI/$IMAGE_NAME:latest"
