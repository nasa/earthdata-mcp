"""Tests for the render_visualization MCP tool."""

import json

from tools.render_visualization.tool import render_visualization

PNG = "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.png"


def test_line_chart():
    rows = [{"date": f"2024-06-0{d}", "mean_sst": 290 + d} for d in range(1, 6)]
    result = render_visualization(title="Mean SST", kind="line", rows=rows, x="date", y=["mean_sst"], y_units="K")
    assert not result.is_error
    assert "line chart of mean_sst vs date (5 points)" in result.content[0].text
    assert '"LineChart"' in json.dumps(result.structured_content)


def test_histogram():
    result = render_visualization(title="SST distribution", kind="histogram", values=[1, 2, 2, 3], bins=3)
    assert "histogram of 4 values in 3 bins" in result.content[0].text


def test_images_filter_non_images():
    result = render_visualization(title="Harmony PNGs", kind="image", image_urls=[PNG, PNG.replace(".png", ".tif")])
    text = result.content[0].text
    assert "1 image(s)" in text and "Ignored 1 link" in text


def test_missing_columns_is_an_error():
    result = render_visualization(title="t", kind="bar", rows=[{"a": 1}], x="a", y=["b"])
    assert result.is_error and "columns not found" in result.content[0].text


def test_image_without_images_is_an_error():
    result = render_visualization(title="t", kind="image", image_urls=["https://x.org/a.nc"])
    assert result.is_error
