# Troubleshooting MCP Deployments

A **`503 Service Unavailable`** means the AWS Application Load Balancer has **zero healthy tasks** in the ECS Target Group. The container is either crashing on startup or failing health checks.

## 1. Check CloudWatch Logs (Fastest)

ECS streams stdout/stderr to CloudWatch. Look here first for startup crashes.

1. Open AWS Console -> **CloudWatch** -> **Log Groups**.
1. Open `/ecs/<environment_name>-earthdata-mcp-server`.
1. Check the most recent Log Stream for exceptions.
   - *Common Error:* `ModuleNotFoundError` usually means a new Python directory is missing from the `COPY` block in `McpServerDockerfile`.

## 2. Inspect the ECS Service

If logs are empty, the container might be dying from infrastructure limits.

1. Open AWS Console -> **Amazon ECS** -> **Clusters** -> `<env>-earthdata-mcp-cluster`.
1. Click the service -> **Tasks** tab -> filter by **Stopped**.
1. Click the latest stopped task and check the **Stopped reason** and **Container Exit Code**:
   - **Exit Code 137 (OOM)**: Task ran out of memory. Increase `var.mcp_server_memory`.
   - **Exit Code 1**: Application crashed. Re-check logs.
   - **Failed ELB health checks**: App started but `/mcp/health` didn't return 200.

## 3. Check Target Group Health

If tasks are "Running" but you still see a 503, health checks are failing.

1. Open AWS Console -> **EC2** -> **Target Groups**.
1. Select the `mcp-` prefixed group.
1. Under **Targets**, hover over **Status details** for Unhealthy targets:
   - *Health checks failed*: App started, but `/mcp/health` timed out or returned an error.
   - *Connection refused*: App isn't listening on port 8080.

## 4. Local Reproduction

Run the image locally to isolate Docker issues from AWS environment issues.

```bash
docker build -t mcp-server-local -f McpServerDockerfile .
docker run -p 8080:8080 -e ENVIRONMENT_NAME=dev mcp-server-local
```

Test the health endpoint:

```bash
curl -v http://localhost:8080/mcp/health
```
