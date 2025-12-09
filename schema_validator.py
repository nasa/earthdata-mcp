import os
import json
import importlib.util
import inspect
from pathlib import Path
from jsonschema import validate, ValidationError


def validate_tool_schemas():
    """
    Validates tool outputs by running them with sample input data
    and checking the output against JSON schemas.
    """
    base_dir = Path(__file__).resolve().parent
    tools_dir = base_dir / "tools"
    schema_dir = base_dir / "schemas"

    # Check if directories exist
    if not os.path.exists(tools_dir):
        print(f"Error: {tools_dir} directory not found")
        return False

    if not os.path.exists(schema_dir):
        print(f"Error: {schema_dir} directory not found")
        return False

    all_valid = True

    # Iterate through tool directories
    for tool_name in os.listdir(tools_dir):
        # Skip special files/directories
        if tool_name.startswith("_") or tool_name.startswith("."):
            continue

        tool_folder = os.path.join(tools_dir, tool_name)

        # Skip non-directories
        if not os.path.isdir(tool_folder):
            continue

        # Check manifest.json for enabled status
        manifest_path = os.path.join(tool_folder, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    enabled = manifest.get("enabled", True)
                    # Handle both boolean and string values
                    if enabled is False or enabled == "false":
                        print(f"Skipping {tool_name} (disabled in manifest)")
                        continue
            except Exception as e:
                print(f"Warning: Error reading manifest for {tool_name}: {e}")

        tool_path = os.path.join(tool_folder, "tool.py")

        # Check if tool.py exists
        if not os.path.exists(tool_path):
            print(f"Warning: No tool.py found in {tool_name}")
            continue

        # Look for corresponding schema files
        schema_folder = os.path.join(schema_dir, tool_name)
        output_schema_file = os.path.join(schema_folder, "output.json")
        input_file = os.path.join(schema_folder, "input.json")

        if not os.path.exists(output_schema_file):
            print(f"Warning: No output.json found for {tool_name}")
            continue

        if not os.path.exists(input_file):
            print(f"Warning: No input.json found for {tool_name}")
            continue

        # Load output schema
        try:
            with open(output_schema_file, "r") as f:
                output_schema = json.load(f)
        except Exception as e:
            print(f"Error loading output schema for {tool_name}: {e}")
            all_valid = False
            continue

        # Load input
        try:
            with open(input_file, "r") as f:
                input_data = json.load(f)
        except Exception as e:
            print(f"Error loading input for {tool_name}: {e}")
            all_valid = False
            continue

        # Load the tool module
        try:
            spec = importlib.util.spec_from_file_location(tool_name, tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the main function in the module
            # Look for functions (not classes) that aren't private (don't start with _)
            tool_functions = [
                name
                for name in dir(module)
                if callable(getattr(module, name))
                and not name.startswith("_")
                and inspect.isfunction(
                    getattr(module, name)
                )  # Only functions, not classes
                and getattr(module, name).__module__
                == tool_name  # Defined in this module
            ]

            if not tool_functions:
                print(f"Warning: No callable function found in {tool_name}")
                continue

            # Use the first function found (assuming one main function per tool)
            func_name = tool_functions[0]
            tool_function = getattr(module, func_name)

            print(f"\nTesting {tool_name}.{func_name}()...")
            print(f"  Input: {json.dumps(input_data, indent=2)}")

            # Call the tool function with input data
            try:
                output = tool_function(**input_data)
            except Exception as e:
                print(f"✗ {tool_name} execution failed: {e}")
                import traceback

                traceback.print_exc()
                all_valid = False
                continue

            print(f"  Output: {json.dumps(output, indent=2, default=str)[:200]}...")

            # Validate output against schema
            try:
                validate(instance=output, schema=output_schema)
                print(f"✓ {tool_name} output is valid")
            except ValidationError as e:
                print(f"✗ {tool_name} output validation failed: {e.message}")
                print(f"  Full output: {json.dumps(output, indent=2, default=str)}")
                all_valid = False

        except Exception as e:
            print(f"Error processing {tool_name}: {e}")
            import traceback

            traceback.print_exc()
            all_valid = False

    return all_valid


if __name__ == "__main__":
    validate_tool_schemas()
