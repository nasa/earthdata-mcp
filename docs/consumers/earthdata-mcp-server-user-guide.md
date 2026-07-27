# Earthdata MCP Server User Guide

The Earthdata MCP (Model Context Protocol) Server provides LLM agents with direct access to NASA's Common Metadata Repository (CMR). This integration enables consumers to agentically discover, verify, and access Earth science datasets through natural language interfaces like ChatGPT, Claude, etc. This guide was created to help users connect to and use the Earthdata MCP server in compatible clients.

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
The Earthdata MCP Server configures the following tools to search across the CMR concept types:

*   **`get_keywords`**: Discovers official Earthdata scientific vocabulary terms (from NASA KMS) to translate colloquial user inputs (e.g. "rain") into precise search labels (e.g. "PRECIPITATION AMOUNT").
*   **`get_collections`**: Searches for datasets (collections) using scientific keywords, instruments, platforms, or spatial/temporal constraints.
*   **`get_granules`**: Searches for specific data files (granules) within a collection. Used to verify actual data availability for a given time and location.
*   **`get_services`**: Discovers data access endpoints (OPeNDAP, Harmony) and visualization layers (WMS/WMTS) associated with a collection.
*   **`get_tools`**: Finds web portals (e.g., Giovanni, Worldview) and downloadable software (e.g., Panoply) associated with a collection, returning URLs and deep-linking templates.
*   **`get_citations`**: Discovers citation records (publications, DOIs) associated with a collection, or looks up citations directly by identifier.
*   **`get_variables`**: Discovers scientific variables and measurements associated with a collection, or looks up variables by keyword. Use this to understand specific data parameters (scale, offset, fill values) before downloading or analyzing data.

---

# How should I use the MCP server in my client?
When a client is connected to the MCP server, it receives instructions for how it should interact with the tools. In a chat client, a query like "I want to find the sea surface temperature in the gulf yesterday" will be orchestrated into a series of tool calls and their parameters as determined by the client. The clients are encouraged to follow a **Discover → Verify → Access** pattern, in which keywords, citations, variables, and collections are used to discover appropriate collections, then granules are used to confirm data availability within the selected region, and finally services, tools are used to guide the consumer to the data.

You can ask for data using queries like:
*   **Show me sea surface temperature data for the Gulf yesterday**
*   **Find me interesting datasets that will help me explore the Richat structure**
*   **I want to explore connections between the rise in CO2 levels and the melting of ice in the polar regions**
*   **I want to find datasets that are often cited together with GRACE satellite gravity data**

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

# Authentication
The Earthdata MCP server is open for discovery. No authentication is required to search for collections, granules, keywords, or any other metadata.

However, downloading data files requires a free Earthdata Login account. When the agent provides download URLs or generates access code, you will need to be authenticated before the files will transfer. If you're using earthaccess, it handles login automatically via stored credentials or an interactive prompt.

Collections that require authentication to view their metadata (e.g., restricted datasets) are not available through the MCP server.

---

# Limitations
The Earthdata MCP server is a **discovery** tool. It helps you find and learn about data — it does not process, transform, or deliver data files directly.

*   **No direct file download or streaming.** The server returns metadata and URLs. Downloading requires Earthdata Login and a separate client (browser, `earthaccess`, `wget`).
*   **No server-side subsetting or transformation.** You cannot ask the MCP server to crop, reproject, or reformat data. Use the associated Services (Harmony, OPeNDAP) or Tools (AppEEARS) for that.
*   **No access to restricted collections.** Collections requiring authentication to view their metadata (e.g., ITAR-restricted data) are not available through the MCP server.
*   **Results depend on client LLM quality.** The MCP server provides tools and instructions, but the quality of orchestration (which tools to call, in what order, with what parameters) depends on the AI client. Results may vary between ChatGPT, Claude, Copilot, etc.
*   **Citation coverage is not exhaustive.** The `get_citations` tool surfaces papers indexed in CMR's citation database. Many papers using NASA data are not yet indexed.

---

# Programmatic Access and End-to-end Workflows
Connected clients are instructed to suggest [earthaccess](https://github.com/nsidc/earthaccess) for programmatic data access. When you ask "how do I download this?", the agent will typically generate working Python code using the collection and granule information it already discovered. You don't need to manually translate MCP results into code yourself.

### Combining MCP servers for end-to-end workflows
Depending on your client or IDE, the Earthdata MCP server becomes significantly more powerful when combined with other MCP servers. Many clients support connecting to multiple servers simultaneously, so your agent can discover data, write download code, execute it, and visualize results in a single conversation.

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
| Different results across clients (ChatGPT vs Claude vs Copilot) | Each client's LLM interprets queries differently | Try rephrasing, or be more explicit about the steps you want taken (e.g., "search for collections, then verify granules"). |

---

# Feedback and Issues
If you encounter problems with the Earthdata MCP server (incorrect results, missing data, tool errors, or unexpected behavior), please report them:
*   **MCP server issues:** File an issue in the [Earthdata MCP Github repository](https://github.com/nasa/earthdata-mcp/issues) or contact the Earthdata support team at [support@earthdata.nasa.gov](mailto:support@earthdata.nasa.gov)
*   **Client-specific issues:** If the problem is with how a specific client (ChatGPT, Claude, etc.) interprets results, check that client's documentation or community forums.
