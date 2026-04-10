# Adding a New Tool to the MCP Server

To add a new capability to the Earthdata MCP server, follow these steps to build and register a new tool.

### 1. Create the Tool Directory

Create a new folder under `tools/` with your tool's name (e.g., `tools/get_weather/`).

### 2. Add Required Files

You must include at least three files in your new directory:

**A. `manifest.json`**
This file defines the tool's metadata for the MCP client. The loader automatically registers the tool using this file.

```json
{
    "name": "get_weather",
    "description": "A detailed description of when the LLM should use this tool.",
    "version": "0.1.0",
    "entry_function": "get_weather"
}
```

- **Important:** You MUST include a `"version"` string following Semantic Versioning (SemVer).

**B. `tool.py`**
The actual Python implementation.

- The primary function name must exactly match the `"entry_function"` in your `manifest.json`.
- The function MUST be synchronous (`def`, not `async def`). The server automatically wraps it in an async handler.

```python
from models.tools.get_weather import GetWeatherInput, GetWeatherOutput

def get_weather(location: str) -> dict:
    """Fetches the weather for a location."""
    # FastMCP infers the input schema from the function signature.
    # Using Pydantic parameters (or GetWeatherInput) is recommended.
    return GetWeatherOutput(status="success", temperature=72).model_dump()
```

**C. `output_model.py`**
A Pydantic output model. Keep exactly one `BaseModel` subclass in this file; the loader registers the first matching model it finds when inspecting the module.

```python
from pydantic import BaseModel

class GetWeatherOutput(BaseModel):
    status: str
    temperature: int
```

### 3. Update the Dockerfile (Crucial Step)

If you added a new root-level Python directory (e.g., you created a `prompts/` or `config/` folder outside of `tools/`), you **MUST** update `McpServerDockerfile` to explicitly `COPY` that directory into the container.

*If you forget this, the AWS ECS container will crash with a `ModuleNotFoundError` on startup.*

```dockerfile
# In McpServerDockerfile
COPY models/ models/
COPY tools/ tools/
COPY util/ util/
COPY new_folder/ new_folder/ # Add your new folder here!
```

### 4. Tool Versioning

Every tool must include a `"version"` string in its `manifest.json` following Semantic Versioning (SemVer). You must bump this version whenever you change the tool's inputs, outputs, or LLM-facing behavior.

See **[Versioning Methodology](versioning.md)** for detailed policies on when to bump Major, Minor, or Patch versions for individual tools vs. the entire MCP Server.

### 5. Testing

1. Run the server locally (`uv run server.py http`).
1. Launch the MCP inspector (`npx @modelcontextprotocol/inspector`) to verify the LLM can see your tool's schema.
1. Write `pytest` coverage under the `tests/` directory.
