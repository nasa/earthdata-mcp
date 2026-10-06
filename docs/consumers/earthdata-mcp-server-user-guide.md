# Earthdata MCP Server User Guide

The Earthdata MCP (Model Context Protocol) Server provides LLM agents with direct access to NASA's Common Metadata Repository (CMR) and NASA's Harmony transformation service. This integration enables consumers to agentically discover, verify, access, and transform Earth science datasets through natural language interfaces like ChatGPT, Claude, etc. This guide was created to help users connect to and use the Earthdata MCP server in compatible clients.

## Table of Contents
* [Glossary](#glossary)
* [Connecting a client to the MCP Server](#connecting-a-client-to-the-mcp-server)
  * [ChatGPT.com](#chatgptcom)
  * [Claude.ai](#claudeai)
  * [Claude Code](#claude-code)
  * [Cursor](#cursor)
  * [Github Copilot Chat](#github-copilot-chat)
  * [Connecting Other MCP Clients](#connecting-other-mcp-clients)
* [What tools are available?](#what-tools-are-available)
* [How should I use the MCP server in my client?](#how-should-i-use-the-mcp-server-in-my-client)
* [Tips for Better Queries](#tips-for-better-queries)
* [Example Walkthrough](#example-walkthrough)
* [Example Walkthrough: Server-Side Transformation](#example-walkthrough-server-side-transformation)
* [Authentication](#authentication)
* [Limitations](#limitations)
* [Programmatic Access and End-to-end Workflows](#programmatic-access-and-end-to-end-workflows)
* [Troubleshooting](#troubleshooting)
* [Feedback and Issues](#feedback-and-issues)

---

## Glossary
NASA's Common Metadata Repository (CMR) organizes Earth science data into a hierarchy of concepts. Understanding these terms will help you interpret the results from the MCP server.

| CMR Term | What it means | Example |
| :--- | :--- | :--- |
| **Collection** | A dataset (a named, versioned group of related data files produced by an instrument or model) | "MODIS/Terra Vegetation Indices 16-Day L3 Global 250m" |
| **Granule** | Data files within a collection, covering a specific time and location | `MOD13Q1.A2026161.h13v08.061` |
| **Variable** | A measured quantity stored inside a granule file, with its own units, scale, and dimensions | `_250m_16_days_NDVI` |
| **Service** | A data access or visualization endpoint associated with a collection | OPeNDAP, Harmony subsetting |
| **Tool** | A web application or downloadable software that works with a collection | AppEEARS, Worldview, Panoply |
| **Citation** | A published paper or DOI that references a collection's data | A journal article citing GRACE mascon data |
| **Keyword** | An official term from NASA's controlled vocabulary (GCMD) used to categorize collections | `DEFORESTATION`, `SEA SURFACE TEMPERATURE` |
| **Harmony** | NASA's server-side data transformation service. Performs subsetting, reprojection, and reformatting of data on NASA's cloud infrastructure so you download only what you need, already in the format you want | Cropping a global collection down to a bounding box and converting it to GeoTIFF |
| **Transformation Job** | An asynchronous processing request submitted to Harmony. Runs in the background and produces downloadable result files once complete | A job that subsets 250 granules to the Amazon basin and reprojects them to EPSG:4326 |

---

## Connecting a client to the MCP Server
The Earthdata MCP server can be accessed by any MCP client that supports the Streamable HTTP transport. If you are using a client not listed below, check its documentation for configuration information.

### ChatGPT.com
ChatGPT supports custom MCP server connections using Plugins in Developer Mode (not available on free plans)
1. Open [chatgpt.com](https://chatgpt.com)
2. In **Settings** → **Security and login**, turn on **Developer Mode**
3. In **Settings** → **Plugins** → **Browse Plugins**, click the **+** icon
4. Set the **Name** (eg. Earthdata)
5. Set the **Connection** to `https://cmr.earthdata.nasa.gov/mcp/v1`
6. Set **Authentication** to **No Auth**
7. Check **I understand and want to continue**
8. Click **Create**

After configuring the custom ChatGPT App, the **Earthdata** MCP Server (or your custom-named server) can be used in a new chat by clicking the **+** icon and selecting the server.

### Claude.ai
1. Open [claude.ai](https://claude.ai)
2. In **Settings** → **Connectors** → Click the **Add** dropdown, select **Add custom connector**
3. Set the **Name** (eg. Earthdata)
4. Set the **Remote MCP server URL** to `https://cmr.earthdata.nasa.gov/mcp/v1`
5. Click **Add**

After configuring the custom Connector, the **Earthdata** MCP Server (or your custom-named server) can be used in a new chat by clicking the **+** icon and enabling the server in the Connectors list.

### Claude Code
1. Install the Claude Code CLI
2. Run `claude mcp add --transport http earthdata https://cmr.earthdata.nasa.gov/mcp/v1`

After configuring the custom MCP server, the **Earthdata** MCP server will be available for use in all new chats within the scope. By default, it's scoped to the current project. Use `--scope user` to make it available globally across all projects.

### Cursor
1. Open Cursor
2. Edit `~/.cursor/mcp.json`
3. Add an entry to the **mcpServers** property
```json
{
  "mcpServers": {
    "earthdata": {
      "url": "https://cmr.earthdata.nasa.gov/mcp/v1"
    }
  }
}
```
4. Restart Cursor

After configuring the MCP server, it will be available in new chats.

### Github Copilot Chat
1. Open Github Copilot Chat plugin in VSCode
2. In **Open customizations** → **MCP Servers** → click the **+** icon
3. Select **HTTP (HTTP or Server-Sent Events)**
4. Set the **Server URL** to `https://cmr.earthdata.nasa.gov/mcp/v1`
5. Set the **Server ID** (eg. earthdata)
6. Select a **Configuration Target** (eg. Workspace or Global)

After configuring the MCP server, it will be available in new chats within the scope of the selected configuration target.

## Connecting Other MCP Clients
Any MCP client that supports the **Streamable HTTP** transport can connect to the Earthdata MCP server. If your client is not listed above, use the following connection details:

| Setting | Value |
| :--- | :--- |
| Server URL | `https://cmr.earthdata.nasa.gov/mcp/v1` |
| Transport | Streamable HTTP |
| Authentication | None |

Consult your client's documentation for where to configure remote MCP server connections. Some clients may refer to this as a "remote server," "HTTP server," or "custom connector."

---

# What tools are available?
The Earthdata MCP Server configures the following tools to search across the CMR concept types, plus a set of tools that submit and track server-side data transformation requests through NASA's Harmony service:

## Discovery & Metadata Tools

*   **`get_keywords`**: Discovers official Earthdata scientific vocabulary terms (from NASA KMS) to translate colloquial user inputs (e.g. "rain") into precise search labels (e.g. "PRECIPITATION AMOUNT").
*   **`get_collections`**: Searches for datasets (collections) using scientific keywords, instruments, platforms, or spatial/temporal constraints.
*   **`get_granules`**: Searches for specific data files (granules) within a collection. Used to verify actual data availability for a given time and location.
*   **`get_services`**: Discovers data access endpoints (OPeNDAP, Harmony) and visualization layers (WMS/WMTS) associated with a collection.
*   **`get_tools`**: Finds web portals (e.g., Giovanni, Worldview) and downloadable software (e.g., Panoply) associated with a collection, returning URLs and deep-linking templates.
*   **`get_citations`**: Discovers citation records (publications, DOIs) associated with a collection, or looks up citations directly by identifier.
*   **`get_variables`**: Discovers scientific variables and measurements associated with a collection, or looks up variables by keyword. Use this to understand specific data parameters (scale, offset, fill values) before downloading or analyzing data.


## Data Transformation Tools (Harmony) (require Earthdata Login authentication — see Authentication)

*   **`get_transformation_options`**: Looks up what server-side operations (subsetting, reprojection, reformatting) a collection supports, which services implement them, the available output formats, and the collection's variables. Useful for checking capabilities before or after submitting a job, but is not required beforehand.
*   **`submit_transformation_job`**: Submits a request to subset, reformat, or reproject a collection's data — by bounding box, shapefile, time range, and/or a specific list of granules. Returns a job ID you can track.
*   **`get_transformation_job_status`**: Checks the status and progress of a submitted transformation job, and once complete, returns links to the transformed output files (paginated, 10 at a time by default).
*   **`control_transformation_job`**: Cancels, pauses, or resumes a transformation job that is currently running or paused.

---

# How should I use the MCP server in my client?
When a client is connected to the MCP server, it receives instructions for how it should interact with the tools. In a chat client, a query like "I want to find the sea surface temperature in the gulf yesterday" will be orchestrated into a series of tool calls and their parameters as determined by the client. The clients are encouraged to follow a **Discover → Verify → Access** pattern, in which keywords, citations, variables, and collections are used to discover appropriate collections, then granules are used to confirm data availability within the selected region, and finally services, tools are used to guide the consumer to the data.

You can ask for data using queries like:
*   **Show me sea surface temperature data for the Gulf yesterday**
*   **Find me interesting datasets that will help me explore the Richat structure**
*   **I want to explore connections between the rise in CO2 levels and the melting of ice in the polar regions**
*   **I want to find datasets that are often cited together with GRACE satellite gravity data**
*   **Crop this MODIS NDVI collection to the Amazon basin and give me the output as GeoTIFF**
*   **Subset that sea surface temperature data to my bounding box and reproject it to EPSG:4326**
*   **Cancel that transformation job I started earlier**

---

# Tips for Better Queries
These tips help your AI client produce more accurate, relevant results from the Earthdata MCP server.

**Be specific about where and when**
*   "NDVI data for the Amazon from January to June 2026" will outperform "vegetation data" every time.
*   Including a geographic region and time range lets the system filter out thousands of irrelevant results.

**Use scientific terms when you know them**
*   "Land surface temperature" finds more than "how hot is the ground."
*   Instrument names help too: "MODIS", "Landsat", "VIIRS", "GRACE-FO."
*   If you don't know the right term, just ask — the agent will use `get_keywords` to translate.

**Ask the agent to verify availability**
*   A collection existing doesn't guarantee data for your specific area and time.
*   Prompts like "confirm there are granules for that region" push the agent to run `get_granules` before declaring success.

**Ask for access methods**
*   After finding data, ask "how can I access this?" or "is there a web tool for this?"
*   The agent will check for OPeNDAP endpoints, Harmony subsetting, or web portals like AppEEARS.

**Be specific about the transformation you want**
*   Instead of "process this data," specify the operation: "crop to this bounding box," "convert to NetCDF," "reproject to EPSG:4326."
*   If you're not sure what a collection supports, ask "what transformation options does this collection support?" — the agent will use get_transformation_options to check before or after submitting a job.
*   If a transformation request fails, the agent will tell you it wasn't supported and check get_transformation_options to explain what actually is available for that collection.

**Scope transformation jobs deliberately**
*   Transformation jobs process every granule that matches your request. If your area/time window matches thousands of granules, say so explicitly — e.g., "just process the 10 most recent granules" — so the agent limits the job rather than submitting it against the entire matching set.
*   Large jobs also produce large result-link lists once complete; use the provided cursor to scroll though the results if needed.

**Manage running jobs explicitly**
*   If you need to stop a long-running job, ask the agent to "cancel job [job ID]" or "pause that job." The agent will not stop, pause, or resume a job on its own without being asked.
*   If a pause/resume/cancel request fails, it usually means the job is already in a state that doesn't allow that action (e.g., trying to resume a job that isn't paused). Ask the agent to check the job's current status first.

**Iterate and refine**
*   Start broad ("precipitation data for Africa") and narrow based on what comes back.
*   Ask follow-up questions: "which of those has the highest resolution?" or "which one is updated daily?"

---

# Example Walkthrough
This example shows the full **Discover -> Verify -> Access** workflow in action. The user asks a single natural-language question, and the agent orchestrates multiple tool calls behind the scenes.

### User prompt
> "Show me deforestation data in the Amazon over the last year"

### 1. Discover (Keywords + Collections)
The agent first translates "deforestation" into official NASA vocabulary:

**Tool call:**
`get_keywords(query="deforestation")`

**Result:**
`DEFORESTATION` — "the removal of trees from a locality, either temporary or permanent..."

The agent then searches for collections with actual data (granules) in the Amazon region during the requested time window:

**Tool call:**
```text
get_collections(
  keyword="MODIS vegetation NDVI",
  has_granules=true,
  temporal_start_date="2025-07-01T00:00:00Z",
  temporal_end_date="2026-07-09T23:59:59Z",
  spatial_wkt_geometry="POLYGON((-75 -15, -50 -15, -50 5, -75 5, -75 -15))"
)
```

**Result:** 39 collections found. Top result:

| Field | Value |
| :--- | :--- |
| Collection | MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061 |
| Short name | MOD13Q1 |
| Concept ID | C1748066515-LPCLOUD |
| Resolution | 250m |
| Level | L3 (gridded observations) |
| DOI | 10.5067/MODIS/MOD13Q1.061 |

The agent selects this collection because NDVI (Normalized Difference Vegetation Index) is a standard proxy for detecting deforestation — declining NDVI over time indicates vegetation loss.

### 2. Verify (Granules)
The agent confirms actual data files exist for the user's region and time period:

**Tool call:**
```text
get_granules(
  collection_concept_id="C1748066515-LPCLOUD",
  temporal_start_date="2025-07-01T00:00:00Z",
  temporal_end_date="2026-07-09T23:59:59Z",
  spatial_wkt_geometry="POLYGON((-75 -15, -50 -15, -50 5, -75 5, -75 -15))",
  sort_key="-start_date"
)
```

**Result:** 276 granules confirmed. Most recent:

| Granule | Coverage |
| :--- | :--- |
| MOD13Q1.A2026161.h13v08.061 | Jun 10–25, 2026 |
| MOD13Q1.A2026161.h13v10.061 | Jun 10–25, 2026 |
| MOD13Q1.A2026161.h13v09.061 | Jun 10–25, 2026 |

Data is confirmed available and current.

### 3. Access (Tools + Services)
The agent checks what tools are available for this collection:

**Tool call:**
`get_tools(collection_concept_id="C1748066515-LPCLOUD")`

**Result:**
[AppEEARS](https://appeears.earthdatacloud.nasa.gov/) — a web application for extracting and downloading subsets of geospatial data.

## Final response to user
The agent synthesizes everything into a clear answer:
*   Identified the right dataset (MOD13Q1 NDVI at 250m resolution)
*   Confirmed 276 tiles available covering the Amazon over the past year
*   Recommended AppEEARS for downloading a spatial/temporal subset
*   Noted that Earthdata Login is required for download

---

# Example Walkthrough: Server-Side Transformation
This example shows the **Discover → Verify → Transform** workflow in action, where the user wants the data itself modified server-side — not just downloaded as-is — using the Harmony transformation tools. **All four Harmony tools used below require the user to be authenticated with Earthdata Login.**

### User prompt
> "I need sea surface temperature data near Hawaii for January 2024, cropped to just that area."

### 1. Discover and verify (Collections + Granules)
The agent first finds a matching collection:

**Tool call:**
```text
get_collections(
  keyword="sea surface temperature",
  temporal_start_date="2024-01-01T00:00:00Z",
  temporal_end_date="2024-01-31T23:59:59Z",
  spatial_wkt_geometry="POLYGON((-162 17, -153 17, -153 23, -162 23, -162 17)),
  has_granules: true
)
```

**Result:** 39 collections found. Top result:  C1996881146-POCLOUD.

The agent then confirms actual granules exist for the requested area and time:

**Tool call:**
```text
get_granules(
  collection_concept_id="C1996881146-POCLOUD",
  temporal_start_date="2024-01-01T00:00:00Z",
  temporal_end_date="2024-01-31T23:59:59Z",
  spatial_wkt_geometry="POLYGON((-162 17, -153 17, -153 23, -162 23, -162 17))"
)
```

**Result:** 32 granules confirmed.

### 2. Submit the transformation job
Because the user gave a clear, specific request (crop to the area), the agent submits the job directly rather than checking capabilities first. It reuses the collection concept ID and granule set already confirmed above:

**Tool call:**
```text
submit_transformation_job(
  collection_concept_id="C1996881146-POCLOUD",
  bbox=[-162, 17, -153, 23],
  temporal_start="2024-01-01T00:00:00Z",
  temporal_stop="2024-01-31T23:59:59Z",
  format: "application/x-netcdf4"
)
```

**Result:**
```text
job_id: "b7e2f4a0-1234-4c56-9abc-def012345678"
status: "running"
```

If the user had not already been authenticated with Earthdata Login at this point, this call would instead return an authentication error. The agent would explain that this action requires logging in, prompt the user to authenticate through the MCP client, and retry once authenticated.

### 3. Poll for job status
The agent checks progress, waiting for the job to reach a terminal status:

**Tool call:**
```text
get_transformation_job_status(job_id="b7e2f4a0-1234-4c56-9abc-def012345678")
```

**Result (in progress):**
```text
status: "running"
progress: 45
```

A follow-up check a short time later shows completion:

**Tool call:**
```text
get_transformation_job_status(job_id="b7e2f4a0-1234-4c56-9abc-def012345678")
```

**Result (complete):**
```text
status: "successful"
progress: 100
num_input_granules: 32
links: [
  "https://harmony.earthdata.nasa.gov/.../result_1.nc4",
  "https://harmony.earthdata.nasa.gov/.../result_2.tnc4",
  "https://harmony.earthdata.nasa.gov/.../result_3.nc4".
  ...
]
total_hits: 31
next_cursor: "..."
```

It will return the first 10 links. You can ask for next set of links and another get_transformation_job_status will be called using the cursor to get the next set.

### 4. What if the request wasn't supported?
If the requested combination of parameters isn't supported by the collection's Harmony services, submit_transformation_job returns an error instead of a job ID. In that case, the agent would follow up with:

**Tool call:**
```text
get_transformation_options(collection_concept_id="C1748066515-LPCLOUD")
```

...to check what output formats, subsetting types, and reprojection options are actually available for that collection, then retry the job with corrected parameters and explain the correction to the user.

4. What if the user wants to stop the job early?
If, while a job is still running, the user says "actually, cancel that job," the agent calls:

**Tool call:**
```text
control_transformation_job(job_id="b7e2f4a0-1234-4c56-9abc-def012345678", action="cancel")
```

**Result:**
```text
status: "canceled"
```

The agent only takes this action because the user explicitly asked for it — it will never cancel, pause, or resume a job on its own initiative. If the user instead asked to "pause" or "resume" a job that isn't in a valid state for that action (e.g., resuming a job that was never paused), Harmony returns an error, and the agent would check get_transformation_job_status to clarify the job's actual current state before trying again.

## Final response to user
The agent synthesizes everything into a clear answer:

*   Confirmed 32 granules of sea surface temperature data available near Hawaii for January 2024
*   Submitted a Harmony job to crop that data to the requested area
*   Confirmed the job completed successfully and provided the first page of download links
*   Noted that Earthdata Login was required to submit the job and will also be required to download the result files

---

# Authentication
The Earthdata MCP server supports two distinct levels of access:

**Discovery (no authentication required):** Searching for collections, granules, keywords, variables, services, tools, and citations is open and requires no login. You can discover and verify data availability anonymously.

**Harmony transformation tools (Earthdata Login required):** All four Harmony tools — `get_transformation_options`, `submit_transformation_job`, `get_transformation_job_status`, and `control_transformation_job` — require you to be authenticated with a free Earthdata Login account. This applies even to read-only actions like checking a job's capabilities or status, not just submitting or downloading. If you ask the agent to perform any of these actions and you are not yet authenticated, your MCP client will prompt you to log in with your Earthdata Login credentials; the agent will explain this and retry once you've authenticated.

**Downloading data (Earthdata Login required):** Separately, downloading the actual data files — whether the original granules found via discovery, or the result files produced by a completed Harmony job — also requires Earthdata Login. When the agent provides download URLs or generates access code, you will need to be authenticated before the files will transfer. If you're using `earthaccess`, it handles login automatically via stored credentials or an interactive prompt.

Collections that require authentication to view their metadata (e.g., restricted datasets) are not available through the discovery tools.

---

# Limitations
The Earthdata MCP server helps you discover, verify, and transform data — but it does not download or store data files itself.

*   **No direct file download or streaming.** The server returns metadata and URLs. Downloading requires Earthdata Login and a separate client (browser, `earthaccess`, `wget`).
*   **Harmony tools require authentication for every action.** Unlike the discovery tools, you must be logged in with Earthdata Login to use any of the four Harmony tools, including simply checking a collection's transformation capabilities or polling a job's status.
*   **Server-side transformation is possible, but only where Harmony supports it.** The `submit_transformation_job` tool can subset, reformat, or reproject data server-side via Harmony, but only for collections and operation combinations that Harmony's associated services actually support. Use `get_transformation_options` to check a collection's capabilities if a job fails or before submitting an unusual request.
*   **Transformation jobs run asynchronously and are not instantaneous.** Submitting a job returns immediately with a job ID; the actual processing happens in the background on Harmony's infrastructure and must be polled via `get_transformation_job_status` until it reaches a terminal status.
*   **Job control actions depend on the job's current state.** `control_transformation_job` can only pause/cancel a job that is still active, or resume one that is currently paused. Attempting an invalid transition (e.g., resuming a job that isn't paused) returns an error. The agent will never cancel, pause, or resume a job without being explicitly asked to.
*   **Large, unscoped transformation jobs are discouraged.** A job submitted against a very large, unfiltered set of granules can take a long time to process on Harmony's infrastructure. Agents are instructed to check granule counts first and scope jobs down (via specific granule IDs or a result limit) — but you can help by being explicit about how much data you actually need.
*   **Access to restricted collections.** Collections requiring authentication to view their metadata (e.g., restricted data to specified groups behind CMR Access control lists) are not available through the Discovery and Metadata tools. The Data transformation tools do have access since they authenticate.
*   **Results depend on client LLM quality.** The MCP server provides tools and instructions, but the quality of orchestration (which tools to call, in what order, with what parameters) depends on the AI client. Results may vary between ChatGPT, Claude, Copilot, etc.
*   **Citation coverage is not exhaustive.** The `get_citations` tool surfaces papers indexed in CMR's citation database. Many papers using NASA data are not yet indexed.

---

# Programmatic Access and End-to-end Workflows
Connected clients are instructed to suggest [earthaccess](https://github.com/nsidc/earthaccess) for programmatic data access. When you ask "how do I download this?", the agent will typically generate working Python code using the collection and granule information it already discovered. You don't need to manually translate MCP results into code yourself.

If you instead want the data modified before download — subset, reformatted, or reprojected — the agent will use the `submit_transformation_job` and `get_transformation_job_status` tools (and `control_transformation_job` if you need to cancel/pause/resume the work) to run that transformation through Harmony, then hand you the resulting download links once the job completes. Remember that all of these Harmony actions require you to be logged in with Earthdata Login first.

### Combining MCP servers for end-to-end workflows
Depending on your client or IDE, the Earthdata MCP server becomes significantly more powerful when combined with other MCP servers. Many clients support connecting to multiple servers simultaneously, so your agent can discover data, transform it, write download code, execute it, and visualize results in a single conversation.

For example, pairing the Earthdata MCP server with the [JupyterHub MCP server](https://github.com/jupyterlab/jupyter-mcp-server) allows an agent to:
1.  **Discover** a dataset using the Earthdata MCP server
2.  **Generate** a notebook that downloads and processes the data using `earthaccess`
3.  **Execute** the notebook cells directly in a running Jupyter kernel
4.  **Visualize** the results

In coding environments like Claude Code, Cursor, or VS Code Copilot, the agent can go further: writing scripts, executing them in a terminal, and iterating on the analysis based on the output.

Learn more: [earthaccess documentation](https://earthaccess.readthedocs.io/)

---

# Troubleshooting

| Symptom | Likely cause | Solution |
| :--- | :--- | :--- |
| "No collections found" | Query terms too specific or using non-standard vocabulary | Ask the agent to search with broader terms, or explicitly request a keyword lookup first. Fewer terms = broader CMR search. |
| Collection found, but "no granules" for my area/time | Collection coverage is global/decadal in metadata but has gaps in practice | Try a different collection, broaden the time window, or check if the mission is still active. |
| Agent returns a collection but it has no download links | Collection may be metadata-only (no actual files) or requires authenticated access | Ask the agent to filter by `has_granules=true` or check for associated services. |
| Agent seems to hallucinate data availability | The agent skipped granule verification | Ask explicitly: "verify that granules exist for that location and date." |
| Tool calls are slow or timing out | CMR may be under heavy load, or the query is too broad | Narrow spatial/temporal filters or try again shortly. |
| "Authentication required" when downloading | Data download requires Earthdata Login | Create a free account at [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov/) and log in before downloading. |
| "Authentication required" when checking transformation options, submitting a job, checking job status, or controlling a job | All four Harmony tools require Earthdata Login, even for read-only checks | Log in with your Earthdata Login credentials through your MCP client when prompted, then ask the agent to retry the request. |
| Different results across clients (ChatGPT vs Claude vs Copilot) | Each client's LLM interprets queries differently | Try rephrasing, or be more explicit about the steps you want taken (e.g., "search for collections, then verify granules"). |
| `submit_transformation_job` fails with an "unsupported operation" error | The requested combination of subsetting/reprojection/format isn't supported for that collection | Ask the agent to check `get_transformation_options` for that collection to see what's actually supported, then retry with corrected parameters. |
| Transformation job stays "running" for a long time | Large or complex jobs can take significant time to process on Harmony's infrastructure | Ask the agent to check the job's `progress` percentage, or consider scoping the job to fewer granules next time. |
| Transformation job status shows "failed" or "running_with_errors" | Some or all input granules could not be processed (e.g., corrupt source file, incompatible format) | Check the job's `message` field for details; try resubmitting with a smaller or different granule list. |
| `control_transformation_job` returns an error when trying to cancel, pause, or resume | The job is already in a state that doesn't support the requested action (e.g., resuming a job that isn't paused, or canceling one that already completed) | Ask the agent to check `get_transformation_job_status` first to confirm the job's current state before retrying the control action. |

---

# Feedback and Issues
If you encounter problems with the Earthdata MCP server (incorrect results, missing data, tool errors, or unexpected behavior), please report them:
*   **MCP server issues:** File an issue in the [Earthdata MCP Github repository](https://github.com/nasa/earthdata-mcp/issues) or contact the Earthdata support team at [support@earthdata.nasa.gov](mailto:support@earthdata.nasa.gov)
*   **Client-specific issues:** If the problem is with how a specific client (ChatGPT, Claude, etc.) interprets results, check that client's documentation or community forums.
