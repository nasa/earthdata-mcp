#!/bin/bash
set -e

# Bamboo task: Package source code for deployment
#
# Creates a tarball of the project that can be downloaded by deployment plans.
# This runs in the build plan after source checkout.

echo "Packaging source code for deployment..."

tar -czf earthdata-mcp-deployed-package.tgz \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='htmlcov' \
  --exclude='.terraform' \
  --exclude='*.tfstate*' \
  --exclude='*.tgz' \
  .

echo "Created earthdata-mcp-deployed-package.tgz"
ls -lh earthdata-mcp-deployed-package.tgz
