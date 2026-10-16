# UI Mockups

Three approaches for returning rich UI from MCP tools. All share `mock_data.py` (granule bboxes, SST time series, collection table).

## Case 1 — Terra UI only (`case1_terra_ui.py`)

**How it works:** Tool returns a raw HTML string. The client renders it. Terra web components load from CDN.

**Map:** `<terra-map>` (OpenLayers) with GeoJSON granule footprints  
**Plot:** `<terra-plot>` (Plotly) with SST anomaly line chart  
**No Python UI dep** — just string formatting.

```bash
python case1_terra_ui.py   # → mockup_case1_terra_ui.html  (open in browser)
```

**Tradeoffs:**
- ✅ Full terra styling + map + Plotly natively
- ✅ Zero Python deps beyond FastMCP
- ❌ Client must render HTML (not all MCP clients do)
- ❌ No prefab layout system

---

## Case 2 — Prefab built-in (`case2_prefab.py`)

**How it works:** Uses `prefab-ui` Python package. Compiles to JSON → React renderer.

**Map:** ❌ none — granule data shown as DataTable + cloud cover BarChart instead  
**Plot:** `BarChart` (prefab built-in, not Plotly — limited to bar/radar/sparkline)

```bash
uv add prefab-ui
python case2_prefab.py   # → mockup_case2_prefab.json
```

**Tradeoffs:**
- ✅ Native FastMCP prefab integration
- ✅ Metric tiles, sortable DataTable out of the box
- ❌ No map component
- ❌ No line/scatter chart — bar chart only for time series
- ❌ No terra styling

---

## Case 3 — Hybrid: Prefab layout + Terra UI components (`case3_hybrid.py`)

**How it works:** Prefab provides layout scaffolding (Card, Row, Metric). Terra UI web components are injected via prefab's `HTML()` escape hatch + CDN `<script type=module>` blocks. `Theme(css=...)` adds terra-specific styles.

**Map:** `<terra-map>` inside a prefab `Card`  
**Plot:** `<terra-plot>` inside a prefab `Card`

```bash
uv add prefab-ui
python case3_hybrid.py   # → mockup_case3_hybrid.json
```

**Tradeoffs:**
- ✅ Best of both: terra map/plot + prefab layout/metrics
- ✅ Terra branding/styling
- ⚠️  Depends on prefab supporting `HTML()` escape hatch (verify API)
- ⚠️  CDN dependency at render time for terra components

---

## Recommendation

| Need | Best case |
|------|-----------|
| Quickest to ship, full terra fidelity | **Case 1** |
| Pure prefab ecosystem, no HTML escape | **Case 2** |
| Terra design system + prefab layout | **Case 3** |
