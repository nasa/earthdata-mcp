"""
Case 2: Pure prefab-ui built-in components.

Uses LineChart (not BarChart) for the SST time series — the real package has it.
No map component exists in prefab, so granule footprints become a DataTable.
Outputs a self-contained HTML file via PrefabApp.html().

Install: uv add prefab-ui  (already done)
Run:     python case2_prefab.py  →  mockup_case2_prefab.html
"""

from mock_data import COLLECTIONS, SST_ANOMALY, SST_DATES

from prefab_ui import PrefabApp
from prefab_ui.components.card import Card
from prefab_ui.components.charts import ChartSeries, LineChart, BarChart
from prefab_ui.components.column import Column
from prefab_ui.components.data_table import DataTable, DataTableColumn
from prefab_ui.components.heading import Heading
from prefab_ui.components.metric import Metric
from prefab_ui.components.row import Row
from prefab_ui.themes.base import Theme

# Granule-level data (no map in prefab)
GRANULES = [
    {"id": "G2345678-POCLOUD", "date": "2024-01-15", "bbox": "-125,45,-116,49.5", "cloud_cover": 12},
    {"id": "G2345679-POCLOUD", "date": "2024-01-16", "bbox": "-122,43.5,-114,48",  "cloud_cover": 35},
    {"id": "G2345680-POCLOUD", "date": "2024-01-17", "bbox": "-124.5,46,-117.5,50","cloud_cover":  5},
    {"id": "G2345681-POCLOUD", "date": "2024-01-18", "bbox": "-121,44.5,-113.5,48.5","cloud_cover":60},
    {"id": "G2345682-POCLOUD", "date": "2024-01-19", "bbox": "-126,45.5,-118,49",  "cloud_cover":  8},
]


def build_prefab_app() -> PrefabApp:
    total_granules = sum(c["granules"] for c in COLLECTIONS)
    avg_cloud = sum(g["cloud_cover"] for g in GRANULES) / len(GRANULES)

    metrics = Row(children=[
        Metric(label="Collections",    value=str(len(COLLECTIONS))),
        Metric(label="Total Granules", value=f"{total_granules:,}"),
        Metric(label="Avg Cloud Cover", value=f"{avg_cloud:.0f}%"),
    ])

    # SST anomaly — LineChart (proper time series chart)
    sst_data = [{"month": d, "anomaly": v} for d, v in zip(SST_DATES, SST_ANOMALY)]
    sst_chart = Card(children=[
        Heading("SST Anomaly (°C) — Monthly 2023–2024", level=3),
        LineChart(
            data=sst_data,
            series=[ChartSeries(dataKey="anomaly", label="Anomaly °C")],
            xAxis="month",
            height=260,
            curve="smooth",
            showDots=False,
            showGrid=True,
        ),
    ])

    # Cloud cover per granule — BarChart
    cloud_data = [{"date": g["date"], "cloud": g["cloud_cover"]} for g in GRANULES]
    cloud_chart = Card(children=[
        Heading("Cloud Cover % by Granule", level=3),
        BarChart(
            data=cloud_data,
            series=[ChartSeries(dataKey="cloud", label="Cloud %")],
            xAxis="date",
            height=220,
            barRadius=4,
            showGrid=True,
        ),
    ])

    # Collections DataTable
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

    # Granule footprints table (no map available in prefab)
    granule_table = Card(children=[
        Heading("Granule Footprints (bbox — no map in prefab)", level=3),
        DataTable(
            columns=[
                DataTableColumn(key="id",    header="Granule ID"),
                DataTableColumn(key="date",  header="Date"),
                DataTableColumn(key="bbox",  header="Bounding Box (W,S,E,N)"),
                DataTableColumn(key="cloud", header="Cloud %", align="right"),
            ],
            rows=[
                {"id": g["id"], "date": g["date"], "bbox": g["bbox"], "cloud": str(g["cloud_cover"])}
                for g in GRANULES
            ],
        ),
    ])

    return PrefabApp(
        title="Earthdata Search Results — Prefab",
        view=Column(children=[
            metrics,
            Row(children=[sst_chart, cloud_chart]),
            collections_table,
            granule_table,
        ]),
        mode="dark",
    )


def get_prefab_tool_output() -> str:
    """MCP tool return — self-contained HTML the FastMCP renderer serves."""
    return build_prefab_app().html()


if __name__ == "__main__":
    html = get_prefab_tool_output()
    out = "mockup_case2_prefab.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written → {out}  (open in browser)")
