"""Pinned CDN assets for the map card."""

from __future__ import annotations

TERRA_VERSION = "0.0.205"
TERRA_CSS = f"https://cdn.jsdelivr.net/npm/@nasa-terra/components@{TERRA_VERSION}/cdn/themes/horizon.css"
TERRA_AUTOLOADER = (
    f"https://cdn.jsdelivr.net/npm/@nasa-terra/components@{TERRA_VERSION}"
    "/cdn/terra-ui-components-autoloader.js"
)

OL_JS = "https://cdn.jsdelivr.net/npm/ol@10/dist/ol.js"

GIBS_ORIGIN = "https://gibs.earthdata.nasa.gov"
GITC_ORIGIN = "https://gitc.earthdata.nasa.gov"   # actual WMTS tile server terra-map uses
CMR_ORIGIN = "https://cmr.earthdata.nasa.gov"

_TERRA_RUNTIME_ORIGINS = [
    "https://cdn.jsdelivr.net",
    "https://server.arcgisonline.com",
    "https://basemaps.arcgis.com",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
    "https://unpkg.com",
]


def map_csp_domains() -> dict[str, list[str]]:
    """connect/resource domains the map card needs."""
    origins = _TERRA_RUNTIME_ORIGINS + [GIBS_ORIGIN, GITC_ORIGIN, CMR_ORIGIN]
    return {"connect_domains": origins, "resource_domains": origins}


CSP_PROFILES = {
    "map": map_csp_domains,
}
