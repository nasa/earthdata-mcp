"""Get GeoTIFF bytes to the browser when the source needs Earthdata Login.

Harmony result links redirect unauthenticated requests to Earthdata Login, and
the map runs in a sandboxed iframe that cannot log in. So the server, which has
the user's EDL token while the tool runs, does the authenticated step:

    Harmony link --(Bearer token)--> 3xx to a presigned S3 URL --(no token)--> bytes

Small files are then inlined into the card (base64), so the browser fetches
nothing and CORS/CSP don't apply. Larger files are handed to the browser as the
presigned URL, which needs no token but does need the bucket's CORS to allow it.
The token itself never goes into the card.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin, urlsplit

import requests

logger = logging.getLogger(__name__)

EDL_HOST = "urs.earthdata.nasa.gov"
# Hosts that get the bearer token. Everything else (e.g. presigned S3) gets none:
# S3 rejects requests that carry two auth mechanisms.
TOKEN_HOST_SUFFIXES = ("earthdata.nasa.gov",)
_REDIRECTS = {301, 302, 303, 307, 308}


def inline_max_bytes() -> int:
    """Files up to this size are embedded in the card (default 5 MB)."""
    return int(os.environ.get("VIZ_INLINE_MAX_BYTES", str(5 * 1024 * 1024)))


class DeliveryError(RuntimeError):
    """The file could not be fetched for the card; the message is user-facing."""


@dataclass
class Delivered:
    """What the browser should load: inline bytes, or a URL it can fetch without auth."""

    url: str
    data_b64: str | None = None
    size: int | None = None
    notes: list[str] = field(default_factory=list)


def needs_token(url: str) -> bool:
    """True for hosts that get the bearer token (Earthdata hosts only)."""
    host = urlsplit(url).hostname or ""
    return host.endswith(TOKEN_HOST_SUFFIXES)


def _open(url: str, token: str | None, session: requests.Session) -> requests.Response:
    """GET following redirects by hand, sending the token only to Earthdata hosts."""
    for _ in range(6):
        host = urlsplit(url).hostname or ""
        if host == EDL_HOST:
            raise DeliveryError(
                "Earthdata Login rejected the request (missing or expired token). "
                "Sign in again or generate a new token."
            )
        headers = {"User-Agent": "earthdata-mcp-viz"}
        if token and needs_token(url):
            headers["Authorization"] = f"Bearer {token}"
        resp = session.get(url, headers=headers, allow_redirects=False, stream=True, timeout=60)
        if resp.status_code in _REDIRECTS and resp.headers.get("Location"):
            resp.close()
            url = urljoin(url, resp.headers["Location"])
            continue
        if resp.status_code >= 400:
            resp.close()
            raise DeliveryError(f"HTTP {resp.status_code} fetching {urlsplit(url).hostname}")
        return resp
    raise DeliveryError("too many redirects")


def deliver_geotiff(
    url: str,
    token: str | None,
    max_inline: int | None = None,
    session: requests.Session | None = None,
) -> Delivered:
    """Resolve a GeoTIFF link into something the browser can load without credentials."""
    if not needs_token(url):
        return Delivered(url=url)  # public host: let the browser fetch it directly
    if not token:
        raise DeliveryError("This link needs Earthdata Login, and no user token is available for this call.")

    limit = inline_max_bytes() if max_inline is None else max_inline
    session = session or requests.Session()
    resp = _open(url, token, session)
    try:
        final_url = resp.url or url
        declared = int(resp.headers.get("Content-Length") or 0)
        if declared and declared > limit:
            return Delivered(url=final_url, size=declared, notes=[
                f"File is {declared / 1048576:.1f} MB, too large to embed; the map loads it from the "
                "presigned link, which requires that bucket's CORS to allow the viewer."
            ])
        data = bytearray()
        for chunk in resp.iter_content(1 << 16):
            data.extend(chunk)
            if len(data) > limit:
                return Delivered(url=final_url, size=None, notes=[
                    "File is too large to embed; the map loads it from the presigned link."
                ])
    finally:
        resp.close()

    if bytes(data[:2]) not in (b"II", b"MM"):
        snippet = bytes(data[:120]).decode("utf-8", "replace").replace("\n", " ")
        raise DeliveryError(f"The link did not return a GeoTIFF (starts with {snippet!r}).")
    return Delivered(url=final_url, data_b64=base64.b64encode(bytes(data)).decode("ascii"), size=len(data))


def _fetch_gibs_wms(
    layer_id: str,
    fmt: str,
    date: str,
    bounds: list[float],
    width: int = 512,
    session: requests.Session | None = None,
) -> tuple[str, str | None]:
    """Fetch a GIBS WMS raster for the given bounds. Returns (base64, error) or ('', error)."""
    from util.visualization.config import GIBS_ORIGIN

    west, south, east, north = bounds
    mime = "image/jpeg" if fmt == "jpg" else "image/png"
    height = max(64, min(512, round(width * (north - south) / max(east - west, 0.001))))
    transparent = "" if fmt == "jpg" else "&TRANSPARENT=true"
    url = (
        f"{GIBS_ORIGIN}/wms/epsg4326/best/wms.cgi"
        f"?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1"
        f"&LAYERS={layer_id}&STYLES=&FORMAT={quote(mime)}"
        f"{transparent}&WIDTH={width}&HEIGHT={height}"
        f"&SRS=EPSG:4326&BBOX={west},{south},{east},{north}&TIME={date}"
    )
    sess = session or requests.Session()
    try:
        resp = sess.get(url, headers={"User-Agent": "earthdata-mcp-viz"}, timeout=30)
    except requests.RequestException as exc:
        return "", f"GIBS WMS request failed: {exc}"
    if resp.status_code >= 400:
        return "", f"GIBS WMS returned HTTP {resp.status_code}"
    data = resp.content
    if data[:4] not in (b"\x89PNG", b"\xff\xd8\xff"[:3]) and data[:3] != b"\xff\xd8\xff":
        snippet = data[:80].decode("utf-8", "replace").replace("\n", " ")
        return "", f"GIBS WMS did not return an image ({snippet!r})"
    return base64.b64encode(data).decode("ascii"), None


def prepare_gibs_layers(
    spec,
    bounds: list[float] | None = None,
    session: requests.Session | None = None,
):
    """Fetch GIBS WMS images server-side and embed them in all GibsLayer in a MapSpec.

    Returns (new_spec, notes). Layers that fail to fetch keep their XYZ tile URL as fallback.
    bounds: [W, S, E, N] for the WMS image; falls back to spec.bounds, then global extent.
    """
    from util.visualization.specs import GibsLayer

    img_bounds = bounds or spec.bounds or [-180.0, -90.0, 180.0, 90.0]
    layers, notes = [], []
    for layer in spec.layers:
        if not isinstance(layer, GibsLayer) or layer.image_b64:
            layers.append(layer)
            continue
        label = layer.title or layer.name
        b64, err = _fetch_gibs_wms(layer.layer, layer.format, layer.date, img_bounds, session=session)
        if not b64:
            notes.append(f"{label}: {err}; falling back to client-side tiles.")
            layers.append(layer)
            continue
        layers.append(layer.model_copy(update={"image_b64": b64, "image_bbox": list(img_bounds)}))
    return spec.model_copy(update={"layers": layers}), notes


def prepare_geotiff_layers(spec, token: str | None, session: requests.Session | None = None):
    """Make every GeoTIFF layer in a MapSpec loadable by the browser.

    Returns (new_spec, notes). Layers that can't be fetched are dropped with a note,
    so the card never shows a layer that is guaranteed to fail.
    """
    from util.visualization.specs import (
        GeoTiffLayer,  # local import: specs imports nothing from here
    )

    layers, notes = [], []
    for layer in spec.layers:
        if not isinstance(layer, GeoTiffLayer) or layer.data_b64:
            layers.append(layer)
            continue
        label = layer.title or layer.name
        try:
            got = deliver_geotiff(layer.url, token, session=session)
        except DeliveryError as exc:
            notes.append(f"{label}: {exc}")
            continue
        except requests.RequestException as exc:
            logger.warning("GeoTIFF fetch failed for %s: %s", layer.url, exc)
            notes.append(f"{label}: could not fetch the file ({type(exc).__name__}).")
            continue
        notes.extend(f"{label}: {n}" for n in got.notes)
        layers.append(layer.model_copy(update={"url": got.url, "data_b64": got.data_b64}))
    return spec.model_copy(update={"layers": layers}), notes
