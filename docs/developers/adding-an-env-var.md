# Adding an Environment Variable

If your Python code requires a new environment variable (e.g. `MY_NEW_API_KEY`), you must explicitly plumb it through the deployment pipeline so it is injected into the AWS ECS Fargate container.

Follow these 4 steps to add a new environment variable:

## 1. Update Bamboo CI/CD Deployment Script

The CI/CD pipeline reads variables from the Bamboo UI and exports them for Terraform.

**File:** `terraform/scripts/bamboo/deploy-application.sh`

Add your variable to the top documentation block and export it:

```bash
# | bamboo_MY_NEW_API_KEY           | No       | default_value                  |

# ... later in the file ...
[ -n "$bamboo_MY_NEW_API_KEY" ] && export TF_VAR_my_new_api_key="$bamboo_MY_NEW_API_KEY"
```

## 2. Add the Variable to the Root Terraform

Terraform needs to know this variable exists so it can pass it to the application module.

**File:** `terraform/application/variables.tf`

```hcl
variable "my_new_api_key" {
  description = "API key for external service"
  type        = string
  default     = ""
}
```

**File:** `terraform/application/main.tf`
Pass it into the `module "application"` block:

```hcl
module "application" {
  # ... existing vars ...
  my_new_api_key = var.my_new_api_key
}
```

## 3. Add the Variable to the Application Module

The application module receives the variable and injects it into the ECS task.

**File:** `terraform/modules/application/variables.tf`

```hcl
variable "my_new_api_key" {
  description = "API key for external service"
  type        = string
}
```

**File:** `terraform/modules/application/mcp-server.tf`
Map it into the `environment` array of the `container_definitions` block:

```hcl
      environment = [
        # ... existing env vars ...
        {
          name  = "MY_NEW_API_KEY"
          value = var.my_new_api_key
        }
      ]
```

## 4. Configure the Variable in Bamboo UI

Finally, go to your Bamboo Deployment Project (e.g., SIT environment) and add the variable under the **Variables** tab so the deployment script can read it.

- **Name:** `MY_NEW_API_KEY`
- **Value:** `your-secret-value`
