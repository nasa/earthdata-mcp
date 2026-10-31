"""Renderer-neutral spec for the map card.

Contract between data tools and renderers:

    CMR / tool outputs  ->  MapSpec  ->  map_card (Prefab card)

Nothing in here knows about HTML or terra-ui.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Bounds = Annotated[list[float], Field(min_length=4, max_length=4)]


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


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MapSpec(_Spec):
    """Everything needed to render a map card.

    terra-map renders GIBS imagery automatically when collection_id is set.
    bounds sets the initial viewport.
    """

    title: str = Field(max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    collection_id: str | None = Field(
        default=None,
        description=(
            "CMR concept ID (e.g. 'C1276812859-GES_DISC'). "
            "terra-map loads the collection's GIBS imagery automatically."
        ),
    )
    bounds: Bounds | None = Field(default=None, description="Initial view [W, S, E, N].")
    height: int = Field(default=460, ge=200, le=1200)
    show_coordinates: bool = True
    notes: list[str] = Field(default_factory=list)
    layers: list[dict] = Field(
        default_factory=list,
        description="Custom OL layers to render on top (e.g. GeoTIFF base64). Added via terra-map.addLayer; collection-id still loads normally.",
    )

    @field_validator("bounds")
    @classmethod
    def _bounds(cls, v: list[float] | None) -> list[float] | None:
        return validate_bounds(v) if v is not None else None

    def initial_bounds(self) -> list[float] | None:
        return list(self.bounds) if self.bounds else None
