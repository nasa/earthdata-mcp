"""Settings for map/chart cards: pinned CDN assets and the iframe CSP.

MCP hosts render app tools in a sandboxed iframe whose Content-Security-Policy
is built from the tool's declared domains *at registration time*. Anything the
map fetches at runtime (CDN scripts, basemap tiles, GIBS tiles, GeoTIFF bytes)
must be listed here, or the host's CSP blocks it. Per-call URLs cannot widen
the CSP, so data hosts the server is expected to hand out are listed up front,
and `unlisted_origins()` flags anything outside the list.

Env overrides (comma-separated origins):
    VIZ_EXTRA_CONNECT_DOMAINS    extra fetch/XHR origins (e.g. a new data bucket)
    VIZ_EXTRA_RESOURCE_DOMAINS   extra script/style/img/font origins
    VIZ_ALLOW_LOCALHOST_HTTP     "true" to accept http://localhost URLs (local dev only)
"""

from __future__ import annotations

import os

# Pinned so a CDN "latest" bump can't silently change rendering.
TERRA_VERSION = "0.0.202"
TERRA_CSS = f"https://cdn.jsdelivr.net/npm/@nasa-terra/components@{TERRA_VERSION}/cdn/themes/horizon.css"
TERRA_AUTOLOADER = (
    f"https://cdn.jsdelivr.net/npm/@nasa-terra/components@{TERRA_VERSION}"
    "/cdn/terra-ui-components-autoloader.js"
)
OL_VERSION = "10.11.0"
OL_JS = f"https://cdn.jsdelivr.net/npm/ol@{OL_VERSION}/dist/ol.js"
GEOTIFF_VERSION = "3.0.5"
GEOTIFF_JS = f"https://cdn.jsdelivr.net/npm/geotiff@{GEOTIFF_VERSION}/dist-browser/geotiff.js"

GIBS_ORIGIN = "https://gibs.earthdata.nasa.gov"

# terra-map's built-in basemap, borders and labels, plus its theme fonts and
# the draw-toolbar sprite it references.
_TERRA_RUNTIME_ORIGINS = [
    "https://cdn.jsdelivr.net",
    "https://server.arcgisonline.com",
    "https://basemaps.arcgis.com",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
    "https://unpkg.com",
]

# Where Harmony result links point. /service-results/<bucket>/... is expected to
# redirect to a presigned S3 URL, and CSP connect-src applies to the redirect
# target too, so the bucket origins must be listed. The S3 hosts below are
# inferred from the result URL layout and should be verified against a real
# redirect (and that bucket's CORS policy must allow GET + Range).
HARMONY_RESULT_ORIGINS = [
    "https://harmony.earthdata.nasa.gov",
    "https://harmony.uat.earthdata.nasa.gov",
    "https://harmony-prod-staging.s3.us-west-2.amazonaws.com",
    "https://harmony-uat-staging.s3.us-west-2.amazonaws.com",
    "https://s3.us-west-2.amazonaws.com",
]


def _env_list(name: str) -> list[str]:
    return [v.strip().rstrip("/") for v in os.environ.get(name, "").split(",") if v.strip()]


def allow_localhost_http() -> bool:
    """Whether http://localhost URLs are accepted (local development only)."""
    return os.environ.get("VIZ_ALLOW_LOCALHOST_HTTP", "").strip().lower() in {"1", "true", "yes"}


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def map_csp_domains() -> dict[str, list[str]]:
    """connect/resource domains the map card needs."""
    data = HARMONY_RESULT_ORIGINS + _env_list("VIZ_EXTRA_CONNECT_DOMAINS")
    connect = _TERRA_RUNTIME_ORIGINS + [GIBS_ORIGIN] + data
    resource = _TERRA_RUNTIME_ORIGINS + [GIBS_ORIGIN] + _env_list("VIZ_EXTRA_RESOURCE_DOMAINS")
    if allow_localhost_http():
        connect += ["http://localhost:*", "http://127.0.0.1:*"]
    return {"connect_domains": _dedupe(connect), "resource_domains": _dedupe(resource)}


def viz_csp_domains() -> dict[str, list[str]]:
    """Images in the viz card load via img-src (resource domains)."""
    resource = HARMONY_RESULT_ORIGINS + [GIBS_ORIGIN] + _env_list("VIZ_EXTRA_RESOURCE_DOMAINS")
    if allow_localhost_http():
        resource += ["http://localhost:*", "http://127.0.0.1:*"]
    return {"resource_domains": _dedupe(resource)}


CSP_PROFILES = {"map": map_csp_domains, "viz": viz_csp_domains}


def unlisted_origins(origins: set[str], allowed: list[str]) -> list[str]:
    """Origins not covered by the declared CSP list (exact match or host:* entry)."""
    def covered(origin: str) -> bool:
        for entry in allowed:
            if entry == origin:
                return True
            if entry.endswith(":*") and origin.startswith(entry[:-2]):
                return True
        return False

    return sorted(o for o in origins if not covered(o))
