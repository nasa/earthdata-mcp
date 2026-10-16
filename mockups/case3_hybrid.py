"""
Case 3: Hybrid — Prefab layout + Terra UI web components via Embed.

Strategy:
  - PrefabApp(stylesheets=[terra horizon CSS], scripts=[terra autoloader JS])
    loads terra UI from CDN into the prefab renderer page
  - Embed(html="<terra-time-average-map ...>") injects the terra web components
    into prefab layout cards
  - Prefab handles: layout, Metric KPI tiles, DataTable for collections
  - Terra handles: <terra-time-average-map> map, <terra-time-series> chart

The terra component props (collection, variable, dates, bearerToken) come
directly from CMR tool results — no client-side data fetching needed from Python.

Run: python case3_hybrid.py  →  mockup_case3_hybrid.html
"""

import json

from mock_data import COLLECTIONS, DEFAULT, TERRA_SCENARIOS
from terra_ui_components import TerraBaseWidget

from prefab_ui import PrefabApp
from prefab_ui.components.card import Card
from prefab_ui.components.column import Column
from prefab_ui.components.data_table import DataTable, DataTableColumn
from prefab_ui.components.embed import Embed
from prefab_ui.components.heading import Heading
from prefab_ui.components.metric import Metric
from prefab_ui.components.row import Row
from prefab_ui.themes.base import Theme


_TERRA_LOADER_JS = TerraBaseWidget.get_autoloader()


def _self_contained_embed(body_html: str, height: str, bg: str = "#1c1f26") -> Embed:
    """Wrap terra component HTML in a full document so the CDN loader runs inside the iframe."""
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <script type="module">
{_TERRA_LOADER_JS}
  </script>
  <style>html,body{{margin:0;background:{bg};height:100%}}</style>
</head>
<body>{body_html}</body>
</html>"""
    return Embed(html=html, height=height)


def _map_embed(scenario: dict, bearer_token: str = "") -> Embed:
    body = f"""<terra-time-average-map
  collection="{scenario['collection']}"
  variable="{scenario['variable']}"
  start-date="{scenario['startDate']}"
  end-date="{scenario['endDate']}"
  long-name="{scenario['long_name']}"
  bearer-token="{bearer_token}"
  style="display:block;height:360px;">
</terra-time-average-map>"""
    return _self_contained_embed(body, height="380px")


def _timeseries_embed(scenario: dict, bearer_token: str = "") -> Embed:
    loc = json.dumps(scenario["location"])
    cid = scenario["collection"][:8]
    body = f"""<terra-time-series
  id="ts-{cid}"
  collection="{scenario['collection']}"
  variable="{scenario['variable']}"
  variable-entry-id="{scenario['variableEntryId']}"
  start-date="{scenario['startDate']}"
  end-date="{scenario['endDate']}"
  bearer-token="{bearer_token}"
  style="display:block;height:320px;">
</terra-time-series>
<script type="module">
  await customElements.whenDefined('terra-time-series');
  const el = document.getElementById('ts-{cid}');
  if (el) el.location = {loc};
</script>"""
    return _self_contained_embed(body, height="340px")


def build_hybrid_app(bearer_token: str = "") -> PrefabApp:
    total_granules = sum(c["granules"] for c in COLLECTIONS)

    metrics = Row(children=[
        Metric(label="Collections",    value=str(len(COLLECTIONS))),
        Metric(label="Total Granules", value=f"{total_granules:,}"),
        Metric(label="Date Range",     value=f"{DEFAULT['startDate']} → {DEFAULT['endDate']}"),
    ])

    map_card = Card(children=[
        Heading(f"{TERRA_SCENARIOS[0]['label']} — Time Average Map", level=3),
        _map_embed(TERRA_SCENARIOS[0], bearer_token),
    ])

    ts_card = Card(children=[
        Heading(f"{TERRA_SCENARIOS[1]['label']} — Time Series", level=3),
        _timeseries_embed(TERRA_SCENARIOS[1], bearer_token),
    ])

    collections_table = Card(children=[
        Heading(f"Collections ({len(COLLECTIONS)} results)", level=3),
        DataTable(
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
                for c in COLLECTIONS
            ],
            search=True,
        ),
    ])

    return PrefabApp(
        title="Earthdata — Hybrid (Prefab + Terra UI)",
        view=Column(children=[
            metrics,
            Row(children=[map_card, ts_card]),
            collections_table,
        ]),
        mode="dark",
        theme=Theme(css="terra-time-average-map, terra-time-series { display: block; }"),
    )


def get_hybrid_tool_output(bearer_token: str = "") -> str:
    """MCP tool return — self-contained HTML the FastMCP renderer serves."""
    return build_hybrid_app(bearer_token).html()


if __name__ == "__main__":
    html = get_hybrid_tool_output()
    out = "mockup_case3_hybrid.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written → {out}  (open in browser)")
    print("Note: terra components need a bearerToken for authenticated Earthdata access")
