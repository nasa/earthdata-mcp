"""
CMR Data Collection Module

This module provides functions for fetching data from NASA's Common Metadata Repository (CMR).
It includes utilities for making API requests to CMR, handling pagination, and processing
the retrieved data.
"""

import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

default_headers = {"Client-Id": "cmr-nlp-search"}


def fetch_cmr_data(
    cmr_url,
    method="GET",
    headers=None,
    params=None,
    data=None,
    search_after=None,
    files=None,
):
    """
    Fetch data from the CMR using the search after pagination method.

    This function makes a request to the specified CMR API endpoint,
    handling pagination through the 'search_after' mechanism. It supports
    custom headers and query parameters for CMR API endpoints.

    Parameters:
        cmr_url (str): The URL of the API endpoint.
        method (str): HTTP method to use ('GET' or 'POST'). Default is 'GET'.
        headers (dict, optional): Headers to include in the API request.
        params (dict, optional): Query parameters for the API request.
        data (dict, optional): Data to send in POST request body.
        search_after (str, optional): Value for 'search_after' header.
        files (dict, optional): Files to send in POST request.

    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the request was successful
            - status_code (int): HTTP status code
            - data: Response data (JSON or text)
            - headers: Response headers
            - error (str, optional): Error message if request failed
    """
    try:
        headers = {**default_headers, **(headers or {})}

        if search_after:
            headers["CMR-Search-After"] = search_after

        if method.upper() == "GET":
            response = requests.get(
                url=cmr_url, headers=headers, params=params, timeout=60
            )
        elif method.upper() == "POST":
            response = requests.post(
                url=cmr_url, headers=headers, data=data, timeout=60, files=files
            )
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()

        if response.status_code == 200:
            headers = dict(response.headers)
            try:
                data = response.json()
            except ValueError:
                data = response.text

            return {
                "success": True,
                "status_code": response.status_code,
                "data": data,
                "headers": response.headers,
            }

        # Handle non-200 status codes
        try:
            error_data = response.json()
        except ValueError:
            error_data = response.text

        return {
            "success": False,
            "status_code": response.status_code,
            "error": f"HTTP {response.status_code}: {response.reason}",
            "data": error_data,
            "headers": headers,
        }
    except requests.exceptions.RequestException as exc:
        logger.error("Error fetching data from API: %s", exc)

        headers = (
            dict(getattr(exc.response, "headers", {}))
            if hasattr(exc, "response") and exc.response
            else {}
        )

        status_code = (
            exc.response.status_code
            if hasattr(exc, "response") and exc.response
            else 500
        )

        return {
            "error": str(exc),
            "status_code": status_code,
            "success": False,
            "headers": headers,
            "data": None,
        }
