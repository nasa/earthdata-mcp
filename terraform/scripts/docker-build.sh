#!/bin/bash
set -e

DOCKERFILE=$1
ENVIRONMENT=$2
TAG=$3
REGION=${4:-us-east-1}

echo "DOCKERFILE: $DOCKERFILE, ENVIRONMENT: $ENVIRONMENT, TAG: $TAG, REGION: $REGION"

if [[ "$DOCKERFILE" == "McpServerDockerfile" ]]; then
    IMAGE_NAME="$ENVIRONMENT-earthdata-mcp-server"
elif [[ "$DOCKERFILE" == "MigrationLambdaDockerfile" ]]; then
    IMAGE_NAME="$ENVIRONMENT-earthdata-mcp-migration"
else
    echo "ERROR: Unknown Dockerfile: $DOCKERFILE"
    exit 1
fi

ACCOUNT=$(aws sts get-caller-identity --region $REGION --query "[Account][0]" --output text)
ECR_URI=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com

echo "Building docker image $IMAGE_NAME:$TAG..."
docker build -t $IMAGE_NAME:$TAG --platform linux/amd64 --provenance=false -f ../$DOCKERFILE ..
docker tag $IMAGE_NAME:$TAG $ECR_URI/$IMAGE_NAME:$TAG

echo "Pushing docker image..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI
docker push $ECR_URI/$IMAGE_NAME:$TAG
