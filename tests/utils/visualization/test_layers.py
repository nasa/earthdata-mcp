"""Tests for the layer builder functions in util.visualization.layers."""

from util.visualization.layers import image_layer, vector_layer, wms_layer

# ---------------------------------------------------------------------------
# image_layer
# ---------------------------------------------------------------------------


def test_image_layer_returns_name_and_js():
    """image_layer must return a dict with 'name' and 'js' keys."""
    result = image_layer("data:image/png;base64,ABC", [0, 0, 10, 10], name="my-layer")
    assert result["name"] == "my-layer"
    assert result["js"]


def test_image_layer_data_uri_skips_fetch():
    """For data: URIs the generated JS must use the direct img.src path, not fetch()."""
    result = image_layer("data:image/png;base64,ABC", [0, 0, 10, 10])
    js = result["js"]
    assert "startsWith('data:')" in js
    assert "fetch(_src)" in js  # fetch path still present for non-data URIs


def test_image_layer_extent_is_transformed():
    """The generated JS must call ol.proj.transformExtent with the given extent."""
    result = image_layer("data:image/png;base64,X", [-10.0, 35.0, 40.0, 70.0])
    assert "transformExtent" in result["js"]
    assert "EPSG:4326" in result["js"]
    assert "EPSG:3857" in result["js"]


def test_image_layer_opacity_is_embedded():
    """opacity must appear in the generated JS."""
    result = image_layer("data:image/png;base64,X", [0, 0, 1, 1], opacity=0.42)
    assert "0.42" in result["js"]


def test_image_layer_returns_ol_image_layer():
    """Generated JS must create an ol.layer.Image with an ol.source.ImageCanvas."""
    js = image_layer("data:image/png;base64,X", [0, 0, 1, 1])["js"]
    assert "ol.layer.Image" in js
    assert "ol.source.ImageCanvas" in js


def test_image_layer_is_async_iife():
    """image_layer JS must be an async IIFE so it can be awaited by addLayer."""
    js = image_layer("data:image/png;base64,X", [0, 0, 1, 1])["js"]
    assert "(async()=>" in js
    assert js.rstrip().endswith(")()")


# ---------------------------------------------------------------------------
# wms_layer
# ---------------------------------------------------------------------------


def test_wms_layer_returns_name_and_js():
    """wms_layer must return a dict with 'name' and 'js' keys."""
    result = wms_layer("https://example.com/wms", "LAYER", name="wms")
    assert result["name"] == "wms"
    assert result["js"]


def test_wms_layer_embeds_layer_name_and_url():
    """WMS layer name and endpoint URL must appear in the generated JS."""
    js = wms_layer("https://example.com/wms", "MY_LAYER")["js"]
    assert "MY_LAYER" in js
    assert "https://example.com/wms" in js


def test_wms_layer_uses_fetch_blob():
    """WMS layer must use fetch()→blob URL to avoid canvas taint."""
    js = wms_layer("https://example.com/wms", "L")["js"]
    assert "fetch(" in js
    assert "createObjectURL" in js


def test_wms_layer_uses_wms_params():
    """Generated JS must include core WMS parameters."""
    js = wms_layer("https://example.com/wms", "L")["js"]
    assert "SERVICE: 'WMS'" in js
    assert "GetMap" in js
    assert "EPSG:3857" in js


def test_wms_layer_extra_params_merged():
    """extra_params must be merged into the WMS URLSearchParams."""
    js = wms_layer("https://example.com/wms", "L", extra_params={"TIME": "2024-01-01"})["js"]
    assert "TIME" in js


def test_wms_layer_is_async_iife():
    """wms_layer JS must be an async IIFE so it can be awaited by addLayer."""
    js = wms_layer("https://example.com/wms", "L")["js"]
    assert "(async()=>" in js
    assert js.rstrip().endswith(")()")


# ---------------------------------------------------------------------------
# vector_layer
# ---------------------------------------------------------------------------


def test_vector_layer_returns_name_and_js():
    """vector_layer must return a dict with 'name' and 'js' keys."""
    result = vector_layer([[0.0, 0.0], [10.0, 20.0]], name="pts")
    assert result["name"] == "pts"
    assert result["js"]


def test_vector_layer_embeds_coordinates():
    """All provided coordinates must appear in the generated JS."""
    coords = [[-74.0, 40.7], [2.35, 48.85]]
    js = vector_layer(coords)["js"]
    assert "-74.0" in js
    assert "40.7" in js
    assert "2.35" in js
    assert "48.85" in js


def test_vector_layer_uses_ol_vector():
    """Generated JS must use ol.layer.Vector and ol.source.Vector."""
    js = vector_layer([[0, 0]])["js"]
    assert "ol.layer.Vector" in js
    assert "ol.source.Vector" in js


def test_vector_layer_circle_style():
    """Generated JS must create an ol.style.Circle with the given radius and color."""
    js = vector_layer([[0, 0]], radius=8, color="rgba(255,0,0,1)")["js"]
    assert "ol.style.Circle" in js
    assert '"radius": 8' in js  # value appears in the injected _P JSON header
    assert "rgba(255,0,0,1)" in js


def test_vector_layer_is_not_async():
    """vector_layer JS must NOT be wrapped in an async IIFE — it is synchronous."""
    js = vector_layer([[0, 0]])["js"]
    assert not js.startswith("(async")
