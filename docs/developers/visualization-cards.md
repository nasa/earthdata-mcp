# Map and chart cards (MCP Apps)

Two tools render UI instead of JSON: `render_map` and `render_visualization`. In MCP Apps hosts (Claude, VS Code, etc.) the user sees an interactive card; the model only receives a short text summary. Clients without MCP Apps support get the text summary.

## How it fits together

```
data tools (get_granules, get_transformation_job_status, get_variables, ...)
        │  links, boxes, scale/offset
        ▼
util/visualization/builders.py, gibs.py   → specs.py (MapSpec / VizSpec)   ← the contract
        ▼
map_card.py / viz_card.py                 → Prefab Card
        ▼
result.py: ui_result(card, summary)       → ToolResult(content=summary, structured_content=PrefabApp)
```

- **Specs are renderer-neutral.** `MapSpec` holds `GeoTiffLayer`, `GibsLayer` and `FootprintLayer` entries; `VizSpec` holds chart rows or image URLs. Validation (https only, bounds, GIBS id/date/matrix patterns, colormap names) lives here.
- **The map card** is a Prefab `Embed` whose HTML is a static template (`assets/terra_map.html`) plus a static runtime (`assets/terra_map_runtime.js`). The spec is injected only as escaped JSON in a `<script type="application/json">` element; no spec value is interpolated into code. The runtime waits for `<terra-map>`, then adds OpenLayers layers with `terraMap.addLayer()`.
- **GeoTIFF delivery (`delivery.py`).** Harmony result links redirect unauthenticated requests to Earthdata Login, and the card's iframe can't log in. So `render_map` fetches each Harmony link server-side with the caller's EDL token (`get_access_token()`), follows the redirect to the presigned S3 URL *without* the token (S3 rejects two auth methods), and embeds files up to `VIZ_INLINE_MAX_BYTES` (default 5 MB) in the card as base64. Larger files are handed to the browser as the presigned URL, which needs that bucket's CORS to allow `*`. The token never goes into the card. Layers that can't be fetched are dropped with a note.
- **Drawing.** The runtime decodes the GeoTIFF once with geotiff.js, paints it onto a canvas with the colormap (fill values transparent), and adds it as an `ol.source.ImageStatic` in EPSG:4326, which OpenLayers reprojects onto the Web Mercator map. Rasters larger than 4096 px on a side are read from an overview or resampled. (Handing the file to `ol.source.GeoTIFF` + `WebGLTile` decoded it a second time and rendered nothing for real Harmony output.) Only lat/lon (EPSG:4326) files are supported today.
- **GIBS lookup** uses the CMR tag `edsc.extra.serverless.gibs` (the same source as terra-map's `collection-id` attribute) to get each product's tile matrix set and format.

## The tool-level CSP

App tools render in a sandboxed iframe whose CSP is fixed when the tool is registered. A manifest opts in with:

```json
"app": { "csp_profile": "map", "csp": { "connect_domains": ["https://extra.example.org"] } }
```

`scripts/preview_card.py` writes `preview/map.html`, `preview/card.html` and `preview/tool_result.json` without an MCP host; it reads `EARTHDATA_BEARER_TOKEN` from `.env` to fetch Harmony files the same way the server does.

`csp_profile` names a domain set in `util/visualization/config.py` (`map`, `viz`); `csp` adds more. The loader turns this into `PrefabAppConfig(csp=ResourceCSP(...))`. Environment overrides: `VIZ_EXTRA_CONNECT_DOMAINS`, `VIZ_EXTRA_RESOURCE_DOMAINS`, and `VIZ_ALLOW_LOCALHOST_HTTP=true` for local development.

Embedded files need no CSP entry or CORS. For files loaded by URL, the data host must send CORS headers that allow `*` (the embedded map runs with an opaque `null` origin); without HTTP Range support the runtime downloads the whole file once.

## Pinned front-end versions

`config.py` pins `@nasa-terra/components` (0.0.202), `ol` (10.11.0) and `geotiff` (3.0.5). terra 0.0.202 does not ship the declarative `layers` / `collection-id` map attributes that exist on terra-ui `main`; once a release includes them, GIBS and GeoTIFF layers could be passed as `terraMap.layers = [...]` instead of being built with the separate OpenLayers bundle.

## Adding things

- **A new layer type:** add a model to `specs.py` and the `MapLayer` union, a branch in `map_card._layer_payload`, and a builder in `assets/terra_map_runtime.js`. Add any new origins to `config.py`.
- **Another tool that returns a card:** build a spec with the helpers in `builders.py`, return `ui_result(map_card(spec), summary)`, and add an `"app"` block to its manifest. Keep a tool's existing JSON contract unchanged; prefer a separate render tool if the data tool has an output schema.
- The runtime is inlined into a `<script>` element: it must not contain an HTML comment opener or a script open/close tag, even in comments (a test enforces this).
