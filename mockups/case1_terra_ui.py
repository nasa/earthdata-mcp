"""
Case 1: terra_ui_components Python package → HTML returned from MCP tool.

Uses TerraBaseWidget.get_autoloader() for the correct versioned CDN URLs,
then builds an HTML string with <terra-time-average-map> and <terra-time-series>
web components.  The components connect to NASA Earthdata APIs themselves —
just pass collection/variable/dates/bearerToken as attributes.

The MCP tool returns this HTML string; clients that render HTML show the live
interactive map and time-series chart.

No prefab-ui needed.
"""

import json

from mock_data import COLLECTIONS, DEFAULT, TERRA_SCENARIOS
from terra_ui_components import TerraBaseWidget  # versioned CDN loader


def _autoloader_html() -> str:
    """Convert TerraBaseWidget JS autoloader snippet to an inline <script> tag."""
    js = TerraBaseWidget.get_autoloader()
    # get_autoloader() returns raw JS that injects <link> and <script> into document.head
    return f"<script type='module'>\n{js}\n</script>"


def build_terra_ui_html(bearer_token: str = "") -> str:
    s = DEFAULT
    location_json = json.dumps(s["location"])

    table_rows = "".join(
        f"<tr><td>{c['short_name']}</td>"
        f"<td style='max-width:300px'>{c['title']}</td>"
        f"<td>{c['provider']}</td>"
        f"<td>{c['granules']:,}</td></tr>"
        for c in COLLECTIONS
    )

    # Second scenario for the time-series widget
    s2 = TERRA_SCENARIOS[1]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Earthdata Search Results</title>
  {_autoloader_html()}
  <style>
    body  {{ font-family: system-ui, sans-serif; padding: 16px; background:#0f1117; color:#e0e0e0; margin:0; }}
    h1    {{ color:#17BECF; font-size:1.2rem; margin:0 0 16px; }}
    h3    {{ color:#17BECF; font-size:.95rem; margin:0 0 8px; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }}
    .card {{ background:#1c1f26; border-radius:8px; padding:12px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    th    {{ background:#262b36; padding:6px 8px; text-align:left; color:#17BECF; }}
    td    {{ padding:5px 8px; border-bottom:1px solid #2a2f3a; }}
    terra-time-average-map {{ display:block; height:360px; }}
    terra-time-series      {{ display:block; height:320px; }}
  </style>
</head>
<body>
  <h1>Earthdata Search Results</h1>

  <div class="grid">
    <!-- terra-time-average-map: renders a temporal average map from CMR data -->
    <div class="card">
      <h3>{s['label']} — Time Average Map</h3>
      <terra-time-average-map
        collection="{s['collection']}"
        variable="{s['variable']}"
        start-date="{s['startDate']}"
        end-date="{s['endDate']}"
        long-name="{s['long_name']}"
        bearer-token="{bearer_token}"
      ></terra-time-average-map>
    </div>

    <!-- terra-time-series: renders a time-series chart fetched from CMR -->
    <div class="card">
      <h3>{s2['label']} — Time Series</h3>
      <terra-time-series
        collection="{s2['collection']}"
        variable="{s2['variable']}"
        variable-entry-id="{s2['variableEntryId']}"
        start-date="{s2['startDate']}"
        end-date="{s2['endDate']}"
        bearer-token="{bearer_token}"
      ></terra-time-series>
      <script type="module">
        await customElements.whenDefined('terra-time-series');
        document.querySelector('terra-time-series').location = {location_json};
      </script>
    </div>
  </div>

  <!-- Collections table -->
  <div class="card">
    <h3>Collections ({len(COLLECTIONS)} results)</h3>
    <table>
      <thead><tr><th>Short Name</th><th>Title</th><th>Provider</th><th>Granules</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>
</body>
</html>"""


def get_terra_ui_tool_output(bearer_token: str = "") -> str:
    """MCP tool return value — HTML string the client renders."""
    return build_terra_ui_html(bearer_token)


if __name__ == "__main__":
    html = get_terra_ui_tool_output()
    out = "mockup_case1_terra_ui.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written → {out}  (open in browser — terra components load from CDN)")
    print("Note: without bearerToken, authenticated CMR endpoints will show login state")
