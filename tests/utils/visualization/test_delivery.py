"""Tests for server-side GeoTIFF delivery (Harmony -> presigned S3, inline embedding)."""

import base64

import pytest
import responses

from util.visualization.delivery import DeliveryError, deliver_geotiff, prepare_geotiff_layers
from util.visualization.specs import FootprintLayer, GeoTiffLayer, MapSpec

HARMONY = "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.tif"
S3 = "https://harmony-prod-staging.s3.us-west-2.amazonaws.com/public/j/1/sst.tif?X-Amz-Signature=abc"
TIFF = b"II*\x00" + b"\x00" * 60


def _harmony_redirects_to_s3(body=TIFF, headers=None):
    responses.add(responses.GET, HARMONY, status=307, headers={"Location": S3})
    responses.add(responses.GET, S3, body=body, status=200, headers=headers or {})


@responses.activate
def test_token_goes_to_harmony_but_not_to_s3():
    _harmony_redirects_to_s3()
    got = deliver_geotiff(HARMONY, "tok")
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"
    assert "Authorization" not in responses.calls[1].request.headers
    assert base64.b64decode(got.data_b64) == TIFF
    assert got.size == len(TIFF)


@responses.activate
def test_large_file_returns_presigned_url_instead_of_bytes():
    _harmony_redirects_to_s3(headers={"Content-Length": str(50 * 1024 * 1024)})
    got = deliver_geotiff(HARMONY, "tok", max_inline=1024)
    assert got.data_b64 is None
    assert got.url == S3
    assert "too large to embed" in got.notes[0]


@responses.activate
def test_stream_cap_without_content_length():
    _harmony_redirects_to_s3(body=TIFF * 100)
    got = deliver_geotiff(HARMONY, "tok", max_inline=100)
    assert got.data_b64 is None and got.url == S3


@responses.activate
def test_login_redirect_is_reported():
    responses.add(responses.GET, HARMONY, status=302,
                  headers={"Location": "https://urs.earthdata.nasa.gov/oauth/authorize?x=1"})
    with pytest.raises(DeliveryError, match="Earthdata Login rejected"):
        deliver_geotiff(HARMONY, "expired")


@responses.activate
def test_non_tiff_body_is_reported():
    _harmony_redirects_to_s3(body=b"<?xml version='1.0'?><Error><Code>AccessDenied</Code></Error>")
    with pytest.raises(DeliveryError, match="did not return a GeoTIFF"):
        deliver_geotiff(HARMONY, "tok")


@responses.activate
def test_http_error_is_reported():
    responses.add(responses.GET, HARMONY, status=404)
    with pytest.raises(DeliveryError, match="HTTP 404"):
        deliver_geotiff(HARMONY, "tok")


def test_no_token_for_earthdata_link():
    with pytest.raises(DeliveryError, match="needs Earthdata Login"):
        deliver_geotiff(HARMONY, None)


def test_public_hosts_pass_through_untouched():
    got = deliver_geotiff("https://example.org/data/a.tif", None)
    assert got.url == "https://example.org/data/a.tif" and got.data_b64 is None


@responses.activate
def test_prepare_layers_embeds_and_drops():
    _harmony_redirects_to_s3()
    bad = HARMONY.replace("sst.tif", "gone.tif")
    responses.add(responses.GET, bad, status=403)
    spec = MapSpec(title="t", layers=[
        GeoTiffLayer(name="ok", url=HARMONY),
        GeoTiffLayer(name="bad", title="Broken", url=bad),
        FootprintLayer(name="area", boxes=[[0, 0, 1, 1]]),
    ])
    out, notes = prepare_geotiff_layers(spec, "tok")
    assert [layer.name for layer in out.layers] == ["ok", "area"]
    assert out.layers[0].data_b64 and out.layers[0].url == S3
    assert notes == ["Broken: HTTP 403 fetching harmony.earthdata.nasa.gov"]
    assert out.data_origins() == set()  # embedded: nothing for the browser to fetch
