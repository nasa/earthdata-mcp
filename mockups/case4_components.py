"""
Case 4: Individual component outputs (hybrid approach).

Each function returns a minimal self-contained HTML string for one component:
  - map_output()        → terra-time-average-map only
  - timeseries_output() → terra-time-series only
  - table_output()      → prefab DataTable only
  - links_output()      → Markdown list of data access links
  - chart_output()      → prefab LineChart only

Run: python case4_components.py  →  mockup_case4_*.html
"""

import json

from mock_data import COLLECTIONS, SST_ANOMALY, SST_DATES, TERRA_SCENARIOS
from terra_ui_components import TerraBaseWidget

from prefab_ui import PrefabApp
from prefab_ui.components.card import Card
from prefab_ui.components.charts import ChartSeries, LineChart
from prefab_ui.components.data_table import DataTable, DataTableColumn
from prefab_ui.components.embed import Embed
from prefab_ui.components.heading import Heading
from prefab_ui.components.markdown import Markdown

_TERRA_LOADER_JS = TerraBaseWidget.get_autoloader()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _terra_iframe(body_html: str, height: str) -> Embed:
    """Full self-contained iframe with terra CDN loader."""
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <script type="module">
{_TERRA_LOADER_JS}
  </script>
  <style>html,body{{margin:0;background:#1c1f26;height:100%}}</style>
</head>
<body>{body_html}</body>
</html>"""
    return Embed(html=html, height=height)


def _app(title: str, view) -> str:
    return PrefabApp(title=title, view=view, mode="dark").html()


# ---------------------------------------------------------------------------
# 1. Map — terra-time-average-map
# ---------------------------------------------------------------------------

def map_output(
    collection: str,
    variable: str,
    start_date: str,
    end_date: str,
    long_name: str = "",
    bearer_token: str = "",
) -> str:
    body = f"""<terra-time-average-map
  collection="{collection}"
  variable="{variable}"
  start-date="{start_date}"
  end-date="{end_date}"
  long-name="{long_name}"
  bearer-token="{bearer_token}"
  style="display:block;height:420px;">
</terra-time-average-map>"""
    return _app(
        f"{long_name or variable} — Map",
        Card(children=[
            Heading(f"{long_name or variable} ({start_date} → {end_date})", level=3),
            _terra_iframe(body, height="440px"),
        ]),
    )


# ---------------------------------------------------------------------------
# 2. Time series — terra-time-series
# ---------------------------------------------------------------------------

def timeseries_output(
    collection: str,
    variable: str,
    variable_entry_id: str,
    start_date: str,
    end_date: str,
    location: dict,
    long_name: str = "",
    bearer_token: str = "",
) -> str:
    loc = json.dumps(location)
    cid = collection[:8]
    body = f"""<terra-time-series
  id="ts-{cid}"
  collection="{collection}"
  variable="{variable}"
  variable-entry-id="{variable_entry_id}"
  start-date="{start_date}"
  end-date="{end_date}"
  bearer-token="{bearer_token}"
  style="display:block;height:340px;">
</terra-time-series>
<script type="module">
  await customElements.whenDefined('terra-time-series');
  const el = document.getElementById('ts-{cid}');
  if (el) el.location = {loc};
</script>"""
    return _app(
        f"{long_name or variable} — Time Series",
        Card(children=[
            Heading(f"{long_name or variable} ({start_date} → {end_date})", level=3),
            _terra_iframe(body, height="360px"),
        ]),
    )


# ---------------------------------------------------------------------------
# 3. Collections table — prefab DataTable
# ---------------------------------------------------------------------------

def table_output(collections: list[dict]) -> str:
    table = DataTable(
        columns=[
            DataTableColumn(key="short_name", header="Short Name"),
            DataTableColumn(key="title",      header="Title"),
            DataTableColumn(key="provider",   header="Provider"),
            DataTableColumn(key="granules",   header="Granules", align="right"),
        ],
        rows=[
            {
                "short_name": c["short_name"],
                "title":      c["title"],
                "provider":   c["provider"],
                "granules":   f"{c['granules']:,}",
            }
            for c in collections
        ],
        search=True,
    )
    return _app(
        f"Collections ({len(collections)} results)",
        Card(children=[
            Heading(f"Collections ({len(collections)} results)", level=3),
            table,
        ]),
    )


# ---------------------------------------------------------------------------
# 4. Data access links — Markdown
# ---------------------------------------------------------------------------

def links_output(collections: list[dict]) -> str:
    lines = ["## Data Access Links\n"]
    for c in collections:
        edsc = f"https://search.earthdata.nasa.gov/search/granules?p={c.get('concept_id', c['short_name'])}"
        lines.append(f"**{c['short_name']}** — {c['title']}")
        lines.append(f"- [Earthdata Search]({edsc})")
        if "opendap_url" in c:
            lines.append(f"- [OPeNDAP]({c['opendap_url']})")
        if "harmony_url" in c:
            lines.append(f"- [Harmony (subset/reproject)]({c['harmony_url']})")
        lines.append("")
    return _app(
        "Data Access Links",
        Card(children=[Markdown(content="\n".join(lines))]),
    )


# ---------------------------------------------------------------------------
# 5. Chart — prefab LineChart (no external fetch, static data)
# ---------------------------------------------------------------------------

def chart_output(
    dates: list[str],
    values: list[float],
    label: str = "Value",
    title: str = "Time Series",
    y_label: str = "",
) -> str:
    data = [{"date": d, "value": v} for d, v in zip(dates, values)]
    chart = LineChart(
        data=data,
        series=[ChartSeries(dataKey="value", label=y_label or label)],
        xAxis="date",
        height=300,
        curve="smooth",
        showDots=False,
        showGrid=True,
    )
    return _app(
        title,
        Card(children=[Heading(title, level=3), chart]),
    )


# ---------------------------------------------------------------------------
# Generate all mockups
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    s0 = TERRA_SCENARIOS[0]
    s1 = TERRA_SCENARIOS[1]

    # Augment COLLECTIONS with concept_id for EDSC links
    collections_with_ids = [
        {**c, "concept_id": c["short_name"]}  # using short_name as stand-in
        for c in COLLECTIONS
    ]

    outputs = [
        ("mockup_case4_map.html",        map_output(
            s0["collection"], s0["variable"], s0["startDate"], s0["endDate"], s0["long_name"],
        )),
        ("mockup_case4_timeseries.html", timeseries_output(
            s1["collection"], s1["variable"], s1["variableEntryId"],
            s1["startDate"], s1["endDate"], s1["location"], s1["long_name"],
        )),
        ("mockup_case4_table.html",      table_output(COLLECTIONS)),
        ("mockup_case4_links.html",      links_output(collections_with_ids)),
        ("mockup_case4_chart.html",      chart_output(
            SST_DATES, SST_ANOMALY,
            label="Anomaly °C",
            title="SST Anomaly — Monthly 2023–2024",
            y_label="°C anomaly",
        )),
    ]

    for fname, html in outputs:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Written → {fname}")
