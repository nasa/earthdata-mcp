# Langfuse Terraform Infrastructure

This repository contains Terraform code to deploy a self-hosted Langfuse instance on AWS using ECS. Langfuse provides observability, evaluations, prompt management, and metrics for LLM applications.

## Architecture Overview

#### The deployment consists of:
- Containerized Services:
  - Langfuse Web UI & API (ECS Fargate)
  - Langfuse Worker (ECS Fargate)
  - ClickHouse for analytics (ECS Fargate)
  - Databases & Storage:

- PostgreSQL (RDS)
  - Redis (ElastiCache)
  - ClickHouse (ECS with EFS storage)
  - S3 Bucket (for event uploads and batch exports)

- Networking & Security:
  - VPC with public/private subnets
  - Security groups for each service
  - Load balancer integration

#### ECS Container Purposes
##### Langfuse Web Container
- Purpose: Serves the main Langfuse web UI and REST APIs
- Port: 3000
- Responsibilities:
  - Web interface for users to view traces, sessions, and analytics
  - REST API endpoints for data ingestion (/api/public/ingestion)
  - User authentication and authorization
  - Project and organization management
  - Health check endpoint (baseurl/api/public/health)
  - Access: External via load balancer at /search/nlp/langfuse

#### Langfuse Worker Container
- Purpose: Background processing and asynchronous task execution
- Port: 3030
- Responsibilities:
  - Processing incoming traces and observations asynchronously
  - Computing analytics and aggregations
  - Batch processing for exports and reports
  - Background database migrations and maintenance tasks
  - Score calculations and evaluations
  - Data pipeline processing for ClickHouse
  - Access: Internal only (health check at /api/health)
```
mcp_terraform/
├── build-langfuse-web-custom.sh    # Script to build custom web image
├── docker-build.sh                 # Script to build worker image
├── data.tf                         # Data sources (VPC, subnets, LB)
├── main.tf                         # Main module calls
├── variables.tf                    # Root variables
├── modules/
│   ├── ecr/                        # ECR repositories
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── langfuse/                   # Main Langfuse infrastructure
│       ├── clickhouse.tf           # ClickHouse ECS service
│       ├── data.tf                 # Module data sources
│       ├── ecs.tf                  # ECS cluster and services
│       ├── efs.tf                  # EFS for ClickHouse storage
│       ├── load_balancer.tf        # Load balancer config
│       ├── postgres.tf             # PostgreSQL database
│       ├── redis.tf                # Redis ElastiCache
│       ├── s3.tf                   # S3 bucket for storage
│       ├── service_discovery.tf    # Service discovery for internal comms
│       ├── storage.tf              # Additional storage config
│       ├── variables.tf            # Module variables
│       └── outputs.tf              # Module outputs
```

Deployment Instructions:

1. Create ECR Repositories
First, create the ECR repositories for the custom images:
`terraform apply -target=module.ecr`
2. Build and Push Docker Images
    Build the custom Langfuse web image (for custom base path):
    ```
    bash
    # For web UI with custom base path
    ./build-langfuse-web-custom.sh langfuse-web-<environment> /search/nlp/langfuse

    # For worker image
    ./docker-build.sh <environment>
    ```
3. Deploy Langfuse Infrastructure
`terraform apply`

### Helpful Link
 [Langfuse v3 Terraform Reference](https://github.com/tubone24/langfuse-v3-terraform)

### Local development
To run Langfuse on local dev machine follow: [Langfuse Docker Compose Deployment](https://langfuse.com/self-hosting/deployment/docker-compose)
