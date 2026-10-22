"""End-to-end: render tools register as MCP Apps and return Prefab UI over a real client."""

import pytest
from fastmcp import Client, FastMCP

from loader import build_app_config, load_tools_from_directory


@pytest.fixture
def server():
    mcp = FastMCP("viz-test")
    load_tools_from_directory(mcp)
    return mcp


class TestBuildAppConfig:
    def test_disabled(self):
        assert build_app_config(None) is None
        assert build_app_config(False) is None

    def test_true_uses_prefab_renderer(self):
        cfg = build_app_config(True)
        assert cfg.resource_uri == "ui://prefab/renderer.html"

    def test_profile_and_extra_domains_merge(self):
        cfg = build_app_config({"csp_profile": "map", "csp": {"connect_domains": ["https://extra.org"]}})
        assert "https://gibs.earthdata.nasa.gov" in cfg.csp.connect_domains
        assert "https://extra.org" in cfg.csp.connect_domains
        assert "https://cdn.jsdelivr.net" in cfg.csp.resource_domains  # prefab renderer + terra

    def test_bad_values(self):
        with pytest.raises(ValueError, match="csp_profile"):
            build_app_config({"csp_profile": "nope"})
        with pytest.raises(ValueError):
            build_app_config("yes")


@pytest.mark.asyncio
async def test_render_tools_are_app_tools(server):
    async with Client(server) as client:
        tools = {t.name: t for t in await client.list_tools()}
        uris = {}
        for name in ("render_map", "render_visualization"):
            ui = (tools[name].meta or {}).get("ui") or {}
            assert ui.get("resourceUri", "").startswith("ui://prefab/"), name
            uris[name] = ui["resourceUri"]
        # FastMCP synthesizes one renderer resource per tool carrying that tool's CSP.
        contents = await client.read_resource(uris["render_map"])
        map_csp = contents[0].meta["ui"]["csp"]
        viz_csp = (await client.read_resource(uris["render_visualization"]))[0].meta["ui"]["csp"]
    assert "https://harmony.earthdata.nasa.gov" in map_csp["connectDomains"]
    assert "https://gibs.earthdata.nasa.gov" in map_csp["resourceDomains"]
    assert "https://harmony.earthdata.nasa.gov" in viz_csp["resourceDomains"]
    # data tools are unchanged
    assert not (tools["get_collections"].meta or {}).get("ui")


@pytest.mark.asyncio
async def test_call_render_map_end_to_end(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "render_map",
            {
                "title": "MUR SST subset",
                "geotiff_urls": [
                    "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.tif"
                ],
                "units": "K",
                "vmin": 271,
                "vmax": 305,
                "bbox": [-40, 30, 20, 70],
            },
        )
    assert not result.is_error
    assert "Rendered an interactive map" in result.content[0].text
    assert "$prefab" in result.structured_content
