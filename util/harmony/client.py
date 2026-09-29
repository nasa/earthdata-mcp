"""Harmony API client."""

import os

from cachetools import TTLCache, cached
from cachetools.keys import hashkey
import harmony

_ENV_MAP = {
    "prod": harmony.Environment.PROD,
    "uat": harmony.Environment.UAT,
    "sit": harmony.Environment.SIT,
    "local": harmony.Environment.LOCAL,
}

# TTL set to 12 hours. EDL token lifetime is 24 hours.
_client_cache: TTLCache = TTLCache(maxsize=256, ttl=43200)


@cached(cache=_client_cache, key=hashkey)
def get_client(token: str) -> harmony.Client:
    """Build (once) and cache the harmony-py Client for this process.

    Deferred until first use so a missing/invalid credential surfaces as a
    tool-call error rather than crashing server startup.
    """
    if not token:
        raise ValueError("A valid token is required to initialize the Harmony client.")

    return harmony.Client(env=harmony_environment(), token=token)

def harmony_environment() -> harmony.Environment:
    """Return harmony environment."""
    name = os.environ.get("HARMONY_ENV", "prod").strip().lower()
    if name not in _ENV_MAP:
        raise ValueError(
            f"Invalid HARMONY_ENV '{name}'. Must be one of: {', '.join(_ENV_MAP)}"
        )
    return _ENV_MAP[name]
