"""Tests for the render_map MCP tool."""

import importlib
import json

import pytest
import responses

TIF = "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.tif"
GIBS_TAGS = {
    "edsc.extra.serverless.gibs": {
        "data": [
            {"product": "GHRSST_L4_MUR_Sea_Surface_Temperature", "title": "MUR SST",
             "format": "png", "geographic_resolution": "1km"},
        ]
    }
}


@pytest.fixture
def tool(monkeypatch):
    module = importlib.import_module("tools.render_map.tool")
    monkeypatch.setattr(module, "fetch_collection_tags", lambda concept_id: GIBS_TAGS)
    # Delivery (server-side fetch with the user's token) is tested separately below
    # and in tests/utils/visualization/test_delivery.py.
    monkeypatch.setattr(module, "prepare_geotiff_layers", lambda spec, token: (spec, []))
    return module


def _text(result) -> str:
    return result.content[0].text


def _view(result) -> str:
    return json.dumps(result.structured_content)


def test_geotiff_from_harmony_links(tool):
    result = tool.render_map(
        title="MUR SST 2024-06-15",
        geotiff_urls=[TIF, TIF.replace(".tif", ".json")],
        units="K", vmin=271, vmax=305, scale=0.001, offset=298.15,
        bbox=[-40, 30, 20, 70],
    )
    assert not result.is_error
    assert result.structured_content["$prefab"]
    text = _text(result)
    assert "GeoTIFF MUR SST 2024-06-15" in text and "Request area" in text
    assert "Ignored 1 non-GeoTIFF link" in text
    assert "not in the map's allowed domains" not in text
    assert "terra-map" in _view(result)


def test_collection_gibs_lookup(tool):
    result = tool.render_map(title="t", collection_concept_id="C2036880657-POCLOUD", gibs_date="2024-06-15")
    view = _view(result)
    assert "GoogleMapsCompatible_Level7" in view and "2024-06-15" in view
    assert "GIBS MUR SST" in _text(result)


def test_collection_without_gibs_reports_it(tool, monkeypatch):
    monkeypatch.setattr(tool, "fetch_collection_tags", lambda concept_id: {})
    result = tool.render_map(title="t", collection_concept_id="C1-X")
    assert result.is_error and "No GIBS imagery" in _text(result)

    result = tool.render_map(title="t", collection_concept_id="C1-X", bbox=[0, 0, 1, 1])
    assert not result.is_error and "No GIBS imagery" in _text(result)


def test_explicit_gibs_layer_uses_tag_resolution_when_known(tool):
    result = tool.render_map(title="t", collection_concept_id="C1-X",
                             gibs_layers=["GHRSST_L4_MUR_Sea_Surface_Temperature", "MODIS_Terra_X"])
    view, text = _view(result), _text(result)
    assert "GoogleMapsCompatible_Level7" in view  # from the tag
    assert "MODIS_Terra_X: resolution unknown" in text


def test_granule_boxes_accept_cmr_strings(tool):
    result = tool.render_map(title="t", granule_boxes=["5.95 34.82 29.5 55.33", [56.07, 15.06, 78.17, 38.7]])
    assert "2 boxes" in _text(result)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({}, "Nothing to draw"),
        ({"geotiff_urls": ["http://insecure.example/a.tif"]}, "https"),
        ({"bbox": [0, 50, 1, 10]}, "south > north"),
        ({"geotiff_urls": [TIF], "colormap": "nope"}, "colormap"),
        ({"granule_boxes": ["1 2 3"]}, "Could not build the map"),
    ],
)
def test_bad_inputs_return_errors_for_the_model(tool, kwargs, message):
    result = tool.render_map(title="t", **kwargs)
    assert result.is_error
    assert message in _text(result)


def test_unlisted_host_is_flagged(tool):
    result = tool.render_map(title="t", geotiff_urls=["https://data.example.org/a.tif"])
    assert "data.example.org" in _text(result) and "VIZ_EXTRA_CONNECT_DOMAINS" in _text(result)


S3 = "https://harmony-prod-staging.s3.us-west-2.amazonaws.com/public/j/1/sst.tif?X-Amz-Signature=abc"


@pytest.fixture
def real_delivery(monkeypatch):
    module = importlib.import_module("tools.render_map.tool")
    monkeypatch.setattr(module, "fetch_collection_tags", lambda concept_id: {})
    return module


@responses.activate
def test_harmony_file_is_fetched_with_user_token_and_embedded(real_delivery, monkeypatch):
    monkeypatch.setattr(real_delivery, "_user_token", lambda: "user-token")
    responses.add(responses.GET, TIF, status=307, headers={"Location": S3})
    responses.add(responses.GET, S3, body=b"II*\x00" + b"\x00" * 60)
    result = real_delivery.render_map(title="t", geotiff_urls=[TIF])
    assert not result.is_error
    assert responses.calls[0].request.headers["Authorization"] == "Bearer user-token"
    view = _view(result)
    assert "user-token" not in view  # the token never goes into the card
    assert "SUkqAA" in view  # base64 of the TIFF header, embedded


def test_harmony_file_without_login_is_reported(real_delivery, monkeypatch):
    monkeypatch.setattr(real_delivery, "_user_token", lambda: None)
    result = real_delivery.render_map(title="t", geotiff_urls=[TIF])
    assert result.is_error and "needs Earthdata Login" in _text(result)
    result = real_delivery.render_map(title="t", geotiff_urls=[TIF], bbox=[0, 0, 1, 1])
    assert not result.is_error and "needs Earthdata Login" in _text(result)
