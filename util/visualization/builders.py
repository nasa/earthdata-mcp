"""Turn existing tool outputs into layer/viz specs.

These are the adapters between data tools and cards, so any tool (or the
render_* tools) can go from "what Harmony/CMR returned" to "what to draw"
without knowing about rendering.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from util.visualization.specs import FootprintLayer, GeoTiffLayer, ImageItem, ValueScale

GEOTIFF_SUFFIXES = (".tif", ".tiff")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _suffix(url: str) -> str:
    return urlparse(url).path.lower().rsplit("/", 1)[-1]


def is_geotiff_url(url: str) -> bool:
    """True for .tif/.tiff links (query strings ignored)."""
    return _suffix(url).endswith(GEOTIFF_SUFFIXES)


def is_image_url(url: str) -> bool:
    """True for browser-displayable image links."""
    return _suffix(url).endswith(IMAGE_SUFFIXES)


def split_result_links(links: Iterable[str]) -> dict[str, list[str]]:
    """Group Harmony result links by what can be drawn with them."""
    groups: dict[str, list[str]] = {"geotiff": [], "image": [], "other": []}
    for url in links:
        key = "geotiff" if is_geotiff_url(url) else "image" if is_image_url(url) else "other"
        groups[key].append(url)
    return groups


def geotiff_layers_from_links(  # pylint: disable=too-many-arguments
    links: Iterable[str],
    title: str | None = None,
    colormap: str = "viridis",
    units: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    scale: float | None = None,
    offset: float | None = None,
    nodata: float | None = None,
    max_layers: int = 4,
) -> list[GeoTiffLayer]:
    """One GeoTiffLayer per .tif link (first visible, the rest hidden, first one fits the view)."""
    value_scale = ValueScale(scale=scale if scale is not None else 1.0, offset=offset or 0.0) if (
        scale is not None or offset is not None
    ) else None
    layers = []
    for i, url in enumerate(u for u in links if is_geotiff_url(u)):
        if i >= max_layers:
            break
        label = urlparse(url).path.rsplit("/", 1)[-1][:120]
        if title:
            label = title if i == 0 else f"{title} ({i + 1})"
        layers.append(
            GeoTiffLayer(
                name=f"geotiff-{i + 1}",
                title=label,
                url=url,
                colormap=colormap,
                units=units,
                vmin=vmin,
                vmax=vmax,
                value_scale=value_scale,
                nodata=nodata,
                visible=i == 0,
                fit=i == 0,
            )
        )
    return layers


def images_from_links(links: Iterable[str], max_images: int = 12) -> list[ImageItem]:
    """ImageItems for the image links, captioned by filename."""
    out = []
    for url in links:
        if is_image_url(url) and len(out) < max_images:
            out.append(ImageItem(url=url, caption=urlparse(url).path.rsplit("/", 1)[-1][:200]))
    return out


def parse_cmr_box(box: str) -> list[float]:
    """CMR granule/collection `boxes` entries are 'S W N E'; return [W, S, E, N]."""
    s, w, n, e = (float(v) for v in box.split())
    return [w, s, e, n]


def footprints_layer(
    boxes: Iterable[list[float]],
    name: str = "footprints",
    title: str = "Footprints",
    color: str = "#00b4ff",
) -> FootprintLayer:
    """An outline layer from [W, S, E, N] boxes."""
    return FootprintLayer(name=name, title=title, boxes=list(boxes), color=color)
