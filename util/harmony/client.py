import os
import datetime
from functools import lru_cache

import harmony

_ENV_MAP = {
    "prod": harmony.Environment.PROD,
    "uat": harmony.Environment.UAT,
    "sit": harmony.Environment.SIT,
    "local": harmony.Environment.LOCAL,
}

def _json_safe(value):
    """Recursively convert datetimes (harmony-py's status() returns some) to ISO strings."""
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value

@lru_cache(maxsize=1)
def get_client(token: str) -> harmony.Client:
    """Build (once) and cache the harmony-py Client for this process.

    Deferred until first use so a missing/invalid credential surfaces as a
    tool-call error rather than crashing server startup.
    """
    if not token:
        raise ValueError("A valid token is required to initialize the Harmony client.")

    return harmony.Client(env=harmony_environment(), token=token)

def harmony_environment() -> harmony.Environment:
    name = os.environ.get("HARMONY_ENV", "prod").strip().lower()
    if name not in _ENV_MAP:
        raise ValueError(
            f"Invalid HARMONY_ENV '{name}'. Must be one of: {', '.join(_ENV_MAP)}"
        )
    return _ENV_MAP[name]
