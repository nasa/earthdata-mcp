"""Tests for the map/viz card renderers."""

import json
import re

from prefab_ui import PrefabApp

from util.visualization import config
from util.visualization.map_card import json_for_script, map_card, map_html, map_payload
from util.visualization.specs import (
    FootprintLayer,
    GeoTiffLayer,
    GibsLayer,
    ImageItem,
    MapSpec,
    Series,
    ValueScale,
    VizSpec,
)
from util.visualization.viz_card import viz_card

TIF = "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.tif"


def _spec(**overrides):
    base = {
        "title": "MUR SST",
        "layers": [
            FootprintLayer(name="area", boxes=[[-40, 30, 20, 70]]),
            GeoTiffLayer(name="sst", url=TIF, units="K", vmin=271, vmax=305,
                         value_scale=ValueScale(scale=0.001, offset=298.15)),
            GibsLayer(name="g", layer="GHRSST_L4_MUR_Sea_Surface_Temperature",
                      tile_matrix_set="GoogleMapsCompatible_Level7", format="png", date="2024-06-15"),
        ],
    }
    return MapSpec(**(base | overrides))


def _embedded_spec(html: str) -> dict:
    match = re.search(r'<script type="application/json" id="map-spec">(.*?)</script>', html, re.S)
    assert match, "spec script missing"
    return json.loads(match.group(1))


class TestMapHtml:
    def test_no_placeholders_left_and_pinned_assets(self):
        html = map_html(_spec())
        assert not re.search(r"__[A-Z_]+__", html)
        for url in (config.OL_JS, config.GEOTIFF_JS, config.TERRA_AUTOLOADER, config.TERRA_CSS):
            assert url in html
        assert "@latest" not in html

    def test_hostile_strings_cannot_break_out_of_the_spec_script(self):
        evil = '</script><script>alert(1)</script><!--'
        html = map_html(_spec(title=evil, layers=[FootprintLayer(name="a", title=evil, boxes=[[0, 0, 1, 1]])]))
        assert evil not in html
        assert html.count("</script>") == html.count("<script")  # nothing extra closed
        assert _embedded_spec(html)["title"] == evil  # still round-trips as data

    def test_inlined_runtime_cannot_confuse_the_html_parser(self):
        from util.visualization.map_card import _asset

        runtime = _asset("terra_map_runtime.js").lower()
        for seq in ("<!--", "<script", "</script"):
            assert seq not in runtime

    def test_runtime_uses_geotiff_v3_async_metadata(self):
        """geotiff.js 3.x made getGDALMetadata async and IFD tags lazy; un-awaited calls silently
        drop the file's scale/offset (verified in headless Chromium against a packed-int16 COG)."""
        from util.visualization.map_card import _asset

        runtime = _asset("terra_map_runtime.js")
        assert "await image.getGDALMetadata(" in runtime
        assert "fileDirectory.getValue" in runtime

    def test_runtime_draws_with_canvas_not_webgl(self):
        """ol.source.GeoTIFF + WebGLTile rendered nothing for real Harmony output, and an
        ImageStatic data: URL is blocked by MCP hosts' img-src CSP (seen in the MCP Inspector).
        The runtime decodes once and draws through ImageCanvas."""
        from util.visualization.map_card import _asset

        runtime = _asset("terra_map_runtime.js")
        assert "new ol.source.ImageCanvas(" in runtime
        assert "toDataURL" not in runtime and "createObjectURL" not in runtime
        assert "new ol.layer.WebGLTile(" not in runtime and "new ol.source.GeoTIFF(" not in runtime

    def test_inline_data_reaches_the_payload(self):
        payload = map_payload(MapSpec(title="t", layers=[GeoTiffLayer(name="a", url=TIF, data_b64="SUkqAA==")]))
        assert payload["layers"][0]["data"] == "SUkqAA=="

    def test_json_for_script_escapes(self):
        assert json_for_script({"a": "<&>"}) == '{"a":"\\u003c\\u0026\\u003e"}'

    def test_payload_order_and_fields(self):
        payload = map_payload(_spec())
        assert [layer["type"] for layer in payload["layers"]] == ["gibs", "geotiff", "footprints"]
        gibs, tif, _ = payload["layers"]
        assert gibs["url"] == (
            "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/GHRSST_L4_MUR_Sea_Surface_Temperature/"
            "default/2024-06-15/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png"
        )
        assert gibs["maxZoom"] == 7
        assert tif["scale"] == 0.001 and tif["offset"] == 298.15 and tif["units"] == "K"
        assert len(tif["colors"]) == 10 and tif["colors"][0] == [68, 1, 84]
        assert payload["bounds"] == [-40, 30, 20, 70]

    def test_scale_left_to_file_when_unset(self):
        payload = map_payload(MapSpec(title="t", layers=[GeoTiffLayer(name="a", url=TIF)]))
        assert payload["layers"][0]["scale"] is None and payload["layers"][0]["offset"] is None
        assert payload["bounds"] is None

    def test_coordinates_attribute(self):
        assert "show-mouse-coordinates" in map_html(_spec())
        assert "show-mouse-coordinates" not in map_html(_spec(show_coordinates=False))


class TestCards:
    def test_map_card_serializes_through_prefab(self):
        data = PrefabApp(title="t", view=map_card(_spec(notes=["note one"]), extra_notes=["note two"])).to_json()
        text = json.dumps(data)
        assert '"Embed"' in text and "note one" in text and "note two" in text
        assert "GHRSST_L4_MUR_Sea_Surface_Temperature" in text

    def test_viz_cards(self):
        line = VizSpec(title="t", kind="line", rows=[{"d": "2024-01", "v": 1}], x="d",
                       series=[Series(key="v", label="Mean")], y_units="K")
        hist = VizSpec(title="t", kind="histogram", values=[1, 2, 3, 4], bins=2)
        imgs = VizSpec(title="t", kind="image", images=[ImageItem(url=TIF.replace(".tif", ".png"), caption="a"),
                                                        ImageItem(url=TIF.replace(".tif", "2.png"))])
        for spec, marker in ((line, "LineChart"), (hist, "BarChart"), (imgs, "Image")):
            text = json.dumps(PrefabApp(view=viz_card(spec)).to_json())
            assert f'"{marker}"' in text
