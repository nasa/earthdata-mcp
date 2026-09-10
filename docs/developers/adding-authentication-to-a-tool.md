# Adding Authentication to a Tool

To add authentication to a tool, you need to update the tool's manifest to include the `require_auth` property.

For example, your `manifest.json` might look like this:

```json
{
  "name": "example_tool",
  "version": "1.0.0",
  "entry_function": "example_tool",
  "require_auth": true <-- This indicates that the tool requires authentication.
}
```

## Using the User's Access Token

After adding the `require_auth` property to the manifest, you can use the user's access token within your tool by importing and calling the `get_access_token` function from `fastmcp.server.dependencies`. For example:

```python
from fastmcp.server.dependencies import get_access_token

token = get_access_token()

# Access token will be available at `token.token`
```
