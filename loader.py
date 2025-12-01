"""
Simplified tool loader.

Convention:
1. Each tool folder has manifest.json with "name" and "description"
2. Each tool folder has tool.py with the tool function
3. Loader handles registration automatically
"""

import json
import importlib
from pathlib import Path
from base_tool import create_simple_tool


def load_tools_from_directory(mcp, tools_dir="tools"):
    """Load all tools from the tools directory."""
    tools_dir = Path(tools_dir)
    loaded = []
    failed = []

    for tool_folder in sorted(tools_dir.iterdir()):
        if not tool_folder.is_dir() or tool_folder.name.startswith((".", "__")):
            continue

        manifest_path = tool_folder / "manifest.json"
        if not manifest_path.exists():
            print(f"[SKIP] {tool_folder.name}: No manifest.json")
            continue

        try:
            # Load manifest
            with open(manifest_path) as f:
                manifest = json.load(f)

            tool_name = manifest.get("name")
            tool_entry = manifest.get("entry_function")
            if not tool_name:
                raise ValueError("manifest.json missing 'name' field")

            # Import the tool module
            module_path = f"{tools_dir.name}.{tool_folder.name}.tool"
            module = importlib.import_module(module_path)

            # Get the tool function
            if not hasattr(module, tool_entry):
                raise AttributeError(f"tool.py missing function '{tool_entry}'")

            tool_func = getattr(module, tool_entry)

            # Register the tool using create_simple_tool
            register_func = create_simple_tool(tool_folder, tool_func)
            register_func(mcp)

            loaded.append(tool_name)
            print(f"[LOAD] ✓ {tool_name}")

        except Exception as e:
            failed.append(tool_folder.name)
            print(f"[FAIL] ✗ {tool_folder.name}: {e}")

    # Summary
    print(f"\n{'='*50}")
    print(f"Loaded: {len(loaded)} tools")
    if failed:
        print(f"Failed: {len(failed)} tools: {', '.join(failed)}")
    print(f"{'='*50}\n")

    return {"loaded": loaded, "failed": failed}
