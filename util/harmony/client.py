import os
from functools import lru_cache

import harmony

_ENV_MAP = {
    "prod": harmony.Environment.PROD,
    "uat": harmony.Environment.UAT,
    "sit": harmony.Environment.SIT,
    "local": harmony.Environment.LOCAL,
}

@lru_cache(maxsize=1)
def get_client(token: str) -> harmony.Client:
    """Build (once) and cache the harmony-py Client for this process.

    Deferred until first use so a missing/invalid credential surfaces as a
    tool-call error rather than crashing server startup.
    """

    kwargs: dict = {"env": harmony_environment()}
    if token:
        kwargs["token"] = token
    elif username and password:
        kwargs["auth"] = (username, password)
    # else: fall back to harmony-py's own .netrc lookup

    return harmony.Client(**kwargs)

def harmony_environment() -> harmony.Environment:
    name = os.environ.get("HARMONY_ENV", "prod").strip().lower()
    if name not in _ENV_MAP:
        raise ValueError(
            f"Invalid HARMONY_ENV '{name}'. Must be one of: {', '.join(_ENV_MAP)}"
        )
    return _ENV_MAP[name]
