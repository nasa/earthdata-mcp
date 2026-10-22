"""VizSpec -> Prefab card (line/bar/scatter/histogram chart, or an image gallery)."""

from __future__ import annotations

from prefab_ui.components.card import Card, CardContent, CardDescription, CardHeader, CardTitle
from prefab_ui.components.charts import BarChart, ChartSeries, LineChart, ScatterChart
from prefab_ui.components.grid import Grid
from prefab_ui.components.histogram import Histogram
from prefab_ui.components.image import Image
from prefab_ui.components.markdown import Markdown
from prefab_ui.components.text import Text

from util.visualization.specs import VizSpec


def _series(spec: VizSpec) -> list[ChartSeries]:
    return [ChartSeries(data_key=s.key, label=s.label or s.key) for s in spec.series]


def _body(spec: VizSpec) -> list:
    if spec.kind == "image":
        figures = []
        for img in spec.images:
            figure = [Image(src=img.url, alt=img.caption or spec.title, width="100%")]
            if img.caption:
                figure.append(Text(img.caption))
            figures.append(figure)
        if len(figures) == 1:
            return figures[0]
        return [Grid(children=[Card(children=f) for f in figures], min_column_width="240px", gap=3)]

    if spec.kind == "histogram":
        return [Histogram(values=spec.values, bins=spec.bins, height=spec.height)]

    if spec.kind == "line":
        return [LineChart(data=spec.rows, series=_series(spec), x_axis=spec.x, height=spec.height)]
    if spec.kind == "bar":
        return [BarChart(data=spec.rows, series=_series(spec), x_axis=spec.x, height=spec.height)]
    return [ScatterChart(data=spec.rows, series=_series(spec), x_axis=spec.x, height=spec.height)]


def viz_card(spec: VizSpec, extra_notes: list[str] | None = None) -> Card:
    """Prefab card: title, chart or images, and caveats."""
    header = [CardTitle(spec.title)]
    subtitle = spec.subtitle
    if spec.y_units and spec.kind not in ("image",):
        subtitle = f"{subtitle} · units: {spec.y_units}" if subtitle else f"Units: {spec.y_units}"
    if subtitle:
        header.append(CardDescription(subtitle))

    content = _body(spec)
    notes = [*spec.notes, *(extra_notes or [])]
    if notes:
        content.append(Markdown(content="\n".join(f"> {n}" for n in notes)))

    return Card(children=[CardHeader(children=header), CardContent(children=content)])
