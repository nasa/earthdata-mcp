#!/bin/bash
set -e

# Bamboo task: Run database migrations
#
# NOTE: This task should normally be DISABLED. Only enable after deploying
#       the database stack or when new migrations are added.
#
# Prerequisites:
#   - Database stack must be deployed
#   - psql must be available on the build agent
#
# Bamboo Variables:
# +---------------------------------+----------+---------+
# | Variable                        | Required | Default |
# +---------------------------------+----------+---------+
# | bamboo_ENVIRONMENT_NAME         | Yes      | -       |
# | bamboo_AWS_ACCESS_KEY_ID        | Yes      | -       |
# | bamboo_AWS_SECRET_ACCESS_KEY    | Yes      | -       |
# | bamboo_AWS_DEFAULT_REGION       | No       | us-east-1 |
# +---------------------------------+----------+---------+

# Set AWS credentials from Bamboo variables
export AWS_DEFAULT_REGION="${bamboo_AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${bamboo_AWS_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${bamboo_AWS_SECRET_ACCESS_KEY}"

ENVIRONMENT="${bamboo_ENVIRONMENT_NAME}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
MIGRATIONS_DIR="${PROJECT_ROOT}/migrations"

echo "Running database migrations"
echo "Environment: $ENVIRONMENT"

if ! command -v psql &> /dev/null; then
    echo "ERROR: psql is not installed on this agent"
    exit 1
fi

SECRET_ID="${ENVIRONMENT}-earthdata-mcp-db"

echo "Fetching database credentials from Secrets Manager..."
DB_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" \
    --query SecretString \
    --output text)

if [ -z "$DB_SECRET" ]; then
    echo "ERROR: Could not fetch secret '$SECRET_ID'"
    exit 1
fi

DB_URL=$(echo "$DB_SECRET" | jq -r '.url')

echo "Running migrations from: $MIGRATIONS_DIR"

for migration in "$MIGRATIONS_DIR"/*.sql; do
    if [ -f "$migration" ]; then
        filename=$(basename "$migration")
        echo "  Running: $filename"
        psql "$DB_URL" -f "$migration"
    fi
done

echo "All migrations completed successfully"
