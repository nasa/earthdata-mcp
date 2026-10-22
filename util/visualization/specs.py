"""Renderer-neutral specs for map and chart cards.

These models are the contract between data tools and renderers:

    Harmony / CMR / GIBS results  ->  MapSpec / VizSpec  ->  Prefab card (map_card / viz_card)

Nothing in here knows about HTML, OpenLayers or terra-ui. A spec can be
built by a tool, by the LLM (via the render_* tool inputs), or in tests, and
rendered by any renderer that understands it.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from util.visualization.colormaps import COLORMAP_NAMES

# [west, south, east, north] in EPSG:4326 degrees. west > east means the box
# crosses the antimeridian.
Bounds = Annotated[list[float], Field(min_length=4, max_length=4)]

_LAYER_NAME = re.compile(r"^[A-Za-z0-9_.:\-]{1,80}$")
_GIBS_ID = re.compile(r"^[A-Za-z0-9_\-]{1,160}$")
_GIBS_DATE = re.compile(r"^(default|\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?)$")
_GIBS_MATRIX = re.compile(r"^GoogleMapsCompatible_Level\d{1,2}$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_bounds(bounds: list[float]) -> list[float]:
    """Check a [W, S, E, N] box is inside valid lon/lat ranges."""
    w, s, e, n = bounds
    if not (-180 <= w <= 180 and -180 <= e <= 180):
        raise ValueError(f"longitude out of range in bounds {bounds}")
    if not (-90 <= s <= 90 and -90 <= n <= 90):
        raise ValueError(f"latitude out of range in bounds {bounds}")
    if s > n:
        raise ValueError(f"south > north in bounds {bounds} (expected [W, S, E, N])")
    return [float(v) for v in bounds]


def validate_http_url(url: str, allow_localhost_http: bool = False) -> str:
    """Accept https URLs (and http://localhost when explicitly allowed)."""
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    if (
        allow_localhost_http
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        return url
    raise ValueError(f"URL must be https: {url}")


def url_origin(url: str) -> str:
    """scheme://host[:port] of a URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Map layers
# --------------------------------------------------------------------------- #


class ValueScale(_Spec):
    """How stored pixel values map to physical values: physical = raw * scale + offset.

    Take these from get_variables (UMM-V Scale/Offset) or the file itself. Leave
    unset when the GeoTIFF already holds physical values (common for float output).
    """

    scale: float = Field(default=1.0, description="Multiply raw values by this.")
    offset: float = Field(default=0.0, description="Then add this.")

    @field_validator("scale")
    @classmethod
    def _nonzero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("scale must be non-zero")
        return v


class _LayerBase(_Spec):
    name: str = Field(description="Unique layer id within the map (letters, digits, _ . : -).")
    title: str | None = Field(default=None, max_length=120, description="Label shown in the legend.")
    opacity: float = Field(default=0.85, ge=0, le=1)
    visible: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not _LAYER_NAME.match(v):
            raise ValueError(f"invalid layer name {v!r}")
        return v


class GeoTiffLayer(_LayerBase):
    """A single-band GeoTIFF / COG, e.g. a Harmony output file."""

    type: Literal["geotiff"] = "geotiff"
    url: str = Field(description="https URL of the GeoTIFF (e.g. a Harmony result link).")
    colormap: str = Field(default="viridis", description=f"One of: {', '.join(COLORMAP_NAMES)}.")
    reverse_colormap: bool = False
    vmin: float | None = Field(default=None, description="Colormap minimum, in physical units. Auto from data if unset.")
    vmax: float | None = Field(default=None, description="Colormap maximum, in physical units. Auto from data if unset.")
    units: str | None = Field(default=None, max_length=40, description="Physical units for the legend/readout, e.g. 'K'.")
    value_scale: ValueScale | None = None
    nodata: float | None = Field(default=None, description="Fill value. Read from the file's GDAL_NODATA tag if unset.")
    fit: bool = Field(default=True, description="Zoom the map to this layer once loaded.")
    data_b64: str | None = Field(
        default=None,
        repr=False,
        description="File bytes, base64, set server-side (util.visualization.delivery) so the browser "
        "needs no network access or credentials. Not a tool input.",
    )

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        from util.visualization.config import allow_localhost_http

        return validate_http_url(v, allow_localhost_http())

    @field_validator("colormap")
    @classmethod
    def _cmap(cls, v: str) -> str:
        if v not in COLORMAP_NAMES:
            raise ValueError(f"unknown colormap {v!r}; choose from {COLORMAP_NAMES}")
        return v

    @model_validator(mode="after")
    def _range(self) -> GeoTiffLayer:
        if self.vmin is not None and self.vmax is not None and self.vmin >= self.vmax:
            raise ValueError("vmin must be less than vmax")
        return self


class GibsLayer(_LayerBase):
    """A NASA GIBS imagery layer (Web Mercator REST tiles)."""

    type: Literal["gibs"] = "gibs"
    layer: str = Field(description="GIBS layer identifier, e.g. 'MODIS_Terra_CorrectedReflectance_TrueColor'.")
    date: str = Field(default="default", description="YYYY-MM-DD, or 'default' for the latest available.")
    tile_matrix_set: str = Field(
        default="GoogleMapsCompatible_Level9",
        description="Must match the layer's resolution (Level6=2km, 7=1km, 8=500m, 9=250m).",
    )
    format: Literal["jpg", "png"] = "jpg"
    opacity: float = Field(default=1.0, ge=0, le=1)

    @field_validator("layer")
    @classmethod
    def _layer(cls, v: str) -> str:
        if not _GIBS_ID.match(v):
            raise ValueError(f"invalid GIBS layer id {v!r}")
        return v

    @field_validator("date")
    @classmethod
    def _date(cls, v: str) -> str:
        if not _GIBS_DATE.match(v):
            raise ValueError("date must be 'default' or YYYY-MM-DD")
        return v

    @field_validator("tile_matrix_set")
    @classmethod
    def _matrix(cls, v: str) -> str:
        if not _GIBS_MATRIX.match(v):
            raise ValueError("tile_matrix_set must look like GoogleMapsCompatible_LevelN")
        return v

    image_b64: str | None = Field(
        default=None,
        repr=False,
        description="WMS image bytes, base64, set server-side. When present the layer renders "
        "as a static ImageCanvas instead of XYZ tiles (avoids iframe CORS/CSP issues).",
    )
    image_bbox: list[float] | None = Field(
        default=None,
        description="[W, S, E, N] bounds of the embedded image, EPSG:4326.",
    )

    @property
    def max_zoom(self) -> int:
        """Deepest zoom level the tile matrix set publishes."""
        return int(self.tile_matrix_set.rsplit("Level", 1)[1])


class FootprintLayer(_LayerBase):
    """Outline boxes, e.g. granule footprints or the requested subset area."""

    type: Literal["footprints"] = "footprints"
    boxes: list[Bounds] = Field(min_length=1, max_length=500, description="[W, S, E, N] boxes in degrees.")
    color: str = Field(default="#00b4ff", description="Hex stroke color.")
    opacity: float = Field(default=1.0, ge=0, le=1)

    @field_validator("boxes")
    @classmethod
    def _boxes(cls, v: list[list[float]]) -> list[list[float]]:
        return [validate_bounds(b) for b in v]

    @field_validator("color")
    @classmethod
    def _color(cls, v: str) -> str:
        if not _HEX_COLOR.match(v):
            raise ValueError("color must be #rrggbb")
        return v


MapLayer = Annotated[GeoTiffLayer | GibsLayer | FootprintLayer, Field(discriminator="type")]


class MapSpec(_Spec):
    """Everything a map card needs."""

    title: str = Field(max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    layers: list[MapLayer] = Field(default_factory=list, max_length=12)
    bounds: Bounds | None = Field(default=None, description="Initial view [W, S, E, N]; derived from layers if unset.")
    height: int = Field(default=460, ge=200, le=1200)
    show_coordinates: bool = True
    notes: list[str] = Field(default_factory=list, description="Caveats shown under the map.")

    @field_validator("bounds")
    @classmethod
    def _bounds(cls, v: list[float] | None) -> list[float] | None:
        return validate_bounds(v) if v is not None else None

    @model_validator(mode="after")
    def _unique_names(self) -> MapSpec:
        names = [layer.name for layer in self.layers]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate layer names: {dupes}")
        return self

    def initial_bounds(self) -> list[float] | None:
        """Explicit bounds, else the union of footprint boxes (GeoTIFFs fit themselves)."""
        if self.bounds:
            return self.bounds
        boxes = [b for layer in self.layers if isinstance(layer, FootprintLayer) for b in layer.boxes]
        if not boxes:
            return None
        return [
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        ]

    def data_origins(self) -> set[str]:
        """Origins the browser must fetch from to draw this spec's data layers."""
        return {
            url_origin(layer.url)
            for layer in self.layers
            if isinstance(layer, GeoTiffLayer) and not layer.data_b64  # embedded files need no fetch
        }


# --------------------------------------------------------------------------- #
# Charts and images
# --------------------------------------------------------------------------- #


class ImageItem(_Spec):
    """One image in a gallery card."""

    url: str
    caption: str | None = Field(default=None, max_length=200)

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        from util.visualization.config import allow_localhost_http

        return validate_http_url(v, allow_localhost_http())


class Series(_Spec):
    """One plotted column."""

    key: str = Field(description="Column in `rows` holding this series' values.")
    label: str | None = None


class VizSpec(_Spec):
    """A chart or image gallery card."""

    title: str = Field(max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    kind: Literal["line", "bar", "scatter", "histogram", "image"]
    rows: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    x: str | None = Field(default=None, description="Column for the x axis (line/bar/scatter).")
    series: list[Series] = Field(default_factory=list, max_length=8)
    values: list[float] = Field(default_factory=list, max_length=100_000, description="Raw values (histogram).")
    bins: int = Field(default=30, ge=2, le=200)
    y_units: str | None = Field(default=None, max_length=40)
    images: list[ImageItem] = Field(default_factory=list, max_length=12)
    height: int = Field(default=320, ge=150, le=1000)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> VizSpec:
        if self.kind == "image":
            if not self.images:
                raise ValueError("kind='image' needs at least one entry in images")
            return self
        if self.kind == "histogram":
            if not self.values:
                raise ValueError("kind='histogram' needs values")
            return self
        if not self.rows or not self.x or not self.series:
            raise ValueError(f"kind={self.kind!r} needs rows, x and series")
        keys = {self.x, *(s.key for s in self.series)}
        missing = sorted(k for k in keys if not any(k in row for row in self.rows))
        if missing:
            raise ValueError(f"columns not found in rows: {missing}")
        return self

    def data_origins(self) -> set[str]:
        """Origins the browser must load images from."""
        return {url_origin(img.url) for img in self.images}
