"""
Utility functions for handling and processing HTTP requests.
"""

import json
import re

import base64
from urllib.parse import parse_qs
from urllib.parse import unquote


def parse_bool(value):
    """
    This function converts various string representations of boolean values
    into actual boolean values. It interprets 'false' (case-insensitive) as False,
    and any other value as True.

    Args:
        value: The value to be parsed. Can be a string, boolean, or any other type.

    Returns:
        bool: False if the lowercase string representation of the value is 'false',
              True for all other inputs.
    """
    return str(value).lower() != "false"


def parse_get_params(event):
    """
    Parse GET parameters from an AWS Lambda event.

    This function extracts 'q' (query), 'spatial', and 'temporal' parameters
    from the queryStringParameters of the provided event dictionary.

    Args:
        event (dict): The AWS Lambda event dictionary containing request information.

    Returns:
        tuple: A tuple containing the query (q), spatial, and temporal parameters.
    """
    params = event.get("queryStringParameters", {}) or {}

    search_params = params.get("search_params", None)
    # if search_params:
    #     search_params = unquote(json.loads(search_params))

    if search_params:
        try:
            search_params = json.loads(unquote(search_params))
        except Exception as exc:
            raise ValueError("search_params must be a valid JSON dictionary") from exc

    return (
        unquote(params.get("q", "")),
        params.get("spatial", ""),
        params.get("temporal", ""),
        parse_bool(params.get("embedding", True)),
        int(params.get("pageNum", 0)),
        int(params.get("pageSize", 10)),
        search_params,
    )


def parse_nested_brackets(key, value, body):
    """
    Parse nested bracket notation like search_params[options][temporal][limit_to_granules].

    Args:
        key: The parameter key with bracket notation
        value: The parameter value
        body: The dictionary to populate
    """
    # Split the key into parts: "search_params[options][temporal][limit_to_granules]"
    # becomes ["search_params", "options][temporal][limit_to_granules]"]
    parts = key.split("[", 1)
    main_key = parts[0]

    if len(parts) == 1:
        # No brackets, simple key
        body[main_key] = value
        return

    # Parse remaining bracket notation: "options][temporal][limit_to_granules]"
    remaining = parts[1]

    # Check if it ends with [] (indicating array)
    is_array = remaining.endswith("[]")
    if is_array:
        remaining = remaining[:-2]  # Remove the []

    # Split by '][' to get nested keys
    if remaining.endswith("]"):
        remaining = remaining[:-1]  # Remove trailing ]

    nested_keys = remaining.split("][")

    # Initialize the main key if it doesn't exist
    if main_key not in body:
        body[main_key] = {}

    # Navigate through nested structure
    current = body[main_key]

    # Create nested structure for all keys except the last one
    for nested_key in nested_keys[:-1]:
        if nested_key not in current:
            current[nested_key] = {}
        current = current[nested_key]

    # Handle the final key
    final_key = nested_keys[-1]

    if is_array:
        # Initialize as array if it doesn't exist
        if final_key not in current:
            current[final_key] = []
        # Ensure it's a list and append the value
        if not isinstance(current[final_key], list):
            current[final_key] = [current[final_key]]
        current[final_key].append(value)
    else:
        # Simple assignment for non-array values
        current[final_key] = value


def _decode_body_if_needed(body_str, is_base64):
    """Decode body string if base64 encoded."""
    if is_base64:
        return base64.b64decode(body_str).decode("utf-8")
    return body_str


def _parse_nested_key(parts):
    """Parse nested key from bracket notation."""
    if len(parts) <= 1:
        return None

    second_part = parts[1]

    if "[" in second_part:
        second_parts = second_part.split("[", 1)
        second_key = second_parts[0].rstrip("]")
        remaining = "[" + second_parts[1]
        return second_key + remaining

    return second_part.rstrip("]")


def _parse_form_encoded_body(body_str, is_base64):
    """Parse application/x-www-form-urlencoded body."""
    decoded_body = _decode_body_if_needed(body_str, is_base64)
    parsed = parse_qs(decoded_body)

    # Convert from lists to single values
    flat_body = {k: v[0] if v else "" for k, v in parsed.items()}

    body = {}
    for k, v in flat_body.items():
        if "[" not in k or "]" not in k:
            body[k] = v
            continue

        is_array = k.endswith("[]")
        k_without_array = k[:-2] if is_array else k

        parts = k_without_array.split("[", 1)
        main = parts[0]

        if main not in body:
            body[main] = {}

        nested_key = _parse_nested_key(parts)
        if nested_key:
            body[main][nested_key] = parsed.get(k, []) if is_array else v

    return body


def _extract_response_params(body):
    """Extract response parameters from parsed body."""
    return (
        body.get("q", ""),
        body.get("spatial", ""),
        body.get("temporal", ""),
        parse_bool(body.get("embedding", True)),
        int(body.get("pageNum", 0)),
        int(body.get("pageSize", 10)),
        body.get("search_params", None),
    )


def parse_post_body(event):
    """
    Parse the body of a POST request from an AWS Lambda event.

    Args:
        event (dict): The AWS Lambda event dictionary.

    Returns:
        tuple: A tuple containing the query (q), spatial, and temporal parameters.
    """
    try:
        headers = event.get("headers", {})
        content_type = headers.get(
            "content-type", headers.get("Content-Type", "")
        ).lower()

        body_str = event.get("body", "")

        if not body_str:
            body = {}
        elif "application/json" in content_type:
            body = json.loads(body_str)
        elif "application/x-www-form-urlencoded" in content_type:
            is_base64 = event.get("isBase64Encoded", False)
            body = _parse_form_encoded_body(body_str, is_base64)
        else:
            body = json.loads(body_str)

        return _extract_response_params(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in request body: {e}") from e


def parse_format(path):
    """
    Parse the requested format from the path.

    Args:
        path (str): The path string to parse.

    Returns:
        str: The parsed format ('json' or 'umm_json').
             Returns 'umm_json' if no match is found.
    """
    match = re.search(r"\.(json|umm_json)$", path or "")

    return match.group(1) if match else "umm_json"


def parse_request_parameters(event):
    """
    Parse request parameters from an AWS Lambda event for both GET and POST
    methods.

    Args:
        event (dict): The AWS Lambda event dictionary containing request
            information.

    Returns:
        tuple: A tuple containing the query (q), spatial, temporal, page
            number, and page size parameters.

    Raises:
        ValueError: If the HTTP method is not supported or if there's an
            error parsing the request body.
    """
    http_method = event.get("httpMethod", "GET")

    if http_method == "GET":
        return parse_get_params(event)
    if http_method == "POST":
        return parse_post_body(event)

    raise ValueError(f"Unsupported HTTP method: {http_method}")


def create_empty_response(response_format):
    """
    Create an empty response structure based on the specified format.

    Args:
        response_format (str): The format of the response, either 'umm_json'
            or json.
    """
    if response_format == "json":
        return {"feed": {"entry": []}}

    return {"items": []}
