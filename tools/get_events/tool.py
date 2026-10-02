"""Query EONET for natural events."""

import logging

import requests
from langfuse import observe

from util.langfuse import trace_update

logger = logging.getLogger(__name__)

def get_events(
    endpoint: str,
    params: dict | None = None,
    limit: int = 10
) -> dict:
    """Send a request to the EONET API to retrieve event data based on specified parameters.
    
    This tool takes an EONET API endpoint name, list of parameters, and a results limit,
    sending a request with this information to the given endpoint. It then returns the
    results of the API call.
    """
    