import os
import json
from pathlib import Path
from jsonschema import validate, ValidationError


def validate_tool_schemas():
    """
    Validate tools using pre-generated sample outputs in CI,
    or by running tools locally.
    """
    base_dir = Path(__file__).resolve().parent
    schema_dir = base_dir / "schemas"
    is_ci = os.getenv("CI", "false").lower() == "true"

    all_valid = True

    for tool_folder in schema_dir.iterdir():
        if not tool_folder.is_dir() or tool_folder.name.startswith(("_", ".")):
            continue

        tool_name = tool_folder.name
        output_schema_file = tool_folder / "output.json"
        sample_output_file = tool_folder / "sample_output.json"

        if not output_schema_file.exists():
            print(f"Warning: No output schema for {tool_name}")
            continue

        # Load schema
        with open(output_schema_file) as f:
            output_schema = json.load(f)

        # In CI: use pre-generated sample
        if is_ci:
            if not sample_output_file.exists():
                print(
                    f"✗ {tool_name}: No sample_output.json (run 'make generate-samples' locally)"
                )
                all_valid = False
                continue

            with open(sample_output_file) as f:
                output = json.load(f)

            print(f"Testing {tool_name} (using sample output)...")

        # Locally: run actual tool
        else:
            input_file = tool_folder / "sample_input.json"
            if not input_file.exists():
                print(f"Warning: No sample_input.json for {tool_name}")
                continue

            with open(input_file) as f:
                input_data = json.load(f)

            print(f"Testing {tool_name} (running tool)...")

            # Try to run the tool
            try:
                output = run_tool(tool_name, input_data)
            except Exception as e:
                print(f"✗ {tool_name} execution failed: {e}")
                all_valid = False
                continue

        # Validate output against schema
        try:
            validate(instance=output, schema=output_schema)
            print(f"✓ {tool_name} output is valid")
        except ValidationError as e:
            print(f"✗ {tool_name} validation failed: {e.message}")
            print(f"  Output: {json.dumps(output, indent=2, default=str)[:500]}")
            all_valid = False

    return all_valid


def run_tool(tool_name, input_data):
    """Run a tool with given input."""
    base_dir = Path(__file__).resolve().parent
    tools_dir = base_dir / "tools"
    tool_path = tools_dir / tool_name / "tool.py"

    import importlib.util
    import inspect

    spec = importlib.util.spec_from_file_location(tool_name, tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find main function
    tool_functions = [
        name
        for name in dir(module)
        if callable(getattr(module, name))
        and not name.startswith("_")
        and inspect.isfunction(getattr(module, name))
        and getattr(module, name).__module__ == tool_name
    ]

    if not tool_functions:
        raise ValueError(f"No function found in {tool_name}")

    func = getattr(module, tool_functions[0])
    return func(**input_data)


def generate_sample_outputs():
    """
    Generate sample outputs locally (where you have API access).
    Run this before committing changes.
    """
    base_dir = Path(__file__).resolve().parent
    tools_dir = base_dir / "tools"
    schema_dir = base_dir / "schemas"

    print("Generating sample outputs (requires API access)...\n")

    for tool_folder in tools_dir.iterdir():
        if not tool_folder.is_dir() or tool_folder.name.startswith(("_", ".")):
            continue

        tool_name = tool_folder.name
        schema_folder = schema_dir / tool_name
        input_file = schema_folder / "sample_input.json"
        sample_output_file = schema_folder / "sample_output.json"

        if not input_file.exists():
            print(f"Skipping {tool_name} (no sample_input.json)")
            continue

        with open(input_file) as f:
            input_data = json.load(f)

        try:
            print(f"Generating output for {tool_name}...")
            output = run_tool(tool_name, input_data)
            print("-" * 50)
            print(schema_folder)
            # Save sample output
            schema_folder.mkdir(exist_ok=True, parents=True)
            with open(sample_output_file, "w") as f:
                json.dump(output, f, indent=2, default=str)

            print(f"✓ Saved to {sample_output_file.relative_to(base_dir)}\n")

        except Exception as e:
            print(f"✗ Failed: {e}\n")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        generate_sample_outputs()
    else:
        success = validate_tool_schemas()
        sys.exit(0 if success else 1)
