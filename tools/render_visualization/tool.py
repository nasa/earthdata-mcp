"""render_visualization: show a chart or Harmony image outputs as a card."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastmcp.tools.base import ToolResult
from langfuse import observe
from pydantic import ValidationError

from util.langfuse import trace_update
from util.visualization import config
from util.visualization.builders import images_from_links
from util.visualization.result import error_result, ui_result
from util.visualization.specs import Series, VizSpec
from util.visualization.viz_card import viz_card

logger = logging.getLogger(__name__)


@observe(name="render_visualization")
def render_visualization(  # pylint: disable=too-many-arguments
    title: str,
    kind: Literal["line", "bar", "scatter", "histogram", "image"],
    rows: list[dict[str, Any]] | None = None,
    x: str | None = None,
    y: list[str] | None = None,
    y_units: str | None = None,
    values: list[float] | None = None,
    bins: int = 30,
    image_urls: list[str] | None = None,
    subtitle: str | None = None,
) -> ToolResult:
    """Render a chart or image card for the user.

    - kind="line" | "bar" | "scatter": pass rows (list of records), x (column for the x axis)
      and y (one or more value columns), e.g. a time series with x="date", y=["mean_sst"].
    - kind="histogram": pass values (raw numbers) and optionally bins.
    - kind="image": pass image_urls, e.g. Harmony result links for a job submitted with
      format="image/png"; non-image links are ignored.

    Only plot numbers that came from tool results or the user; never invent data points.
    The model receives a short text summary, not the rendered chart.
    """
    trace_update(tags=["visualization", "chart"], metadata={"kind": kind, "rows": len(rows or [])})

    notes: list[str] = []
    try:
        images = []
        if kind == "image":
            links = image_urls or []
            images = images_from_links(links)
            if len(images) < len(links):
                notes.append(f"Ignored {len(links) - len(images)} link(s) that are not images.")
        spec = VizSpec(
            title=title,
            subtitle=subtitle,
            kind=kind,
            rows=rows or [],
            x=x,
            series=[Series(key=k) for k in (y or [])],
            values=values or [],
            bins=bins,
            y_units=y_units,
            images=images,
        )
    except ValidationError as exc:
        detail = "; ".join(e["msg"] for e in exc.errors())
        logger.warning("render_visualization input rejected: %s", detail)
        return error_result(f"Could not build the visualization: {detail}")

    blocked = config.unlisted_origins(spec.data_origins(), config.viz_csp_domains()["resource_domains"])
    if blocked:
        notes.append("Images from these hosts may be blocked by the viewer: " + ", ".join(blocked) + ".")

    if kind == "image":
        what = f"{len(spec.images)} image(s)"
    elif kind == "histogram":
        what = f"histogram of {len(spec.values)} values in {spec.bins} bins"
    else:
        what = f"{kind} chart of {', '.join(s.key for s in spec.series)} vs {spec.x} ({len(spec.rows)} points)"
    summary = f"Rendered for the user: {title} — {what}." + (f" Notes: {' '.join(notes)}" if notes else "")
    return ui_result(viz_card(spec, extra_notes=notes), summary, title=title)
