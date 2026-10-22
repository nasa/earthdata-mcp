"""Tests for visualization specs, builders, GIBS resolution and CSP helpers."""

import pytest
from pydantic import ValidationError

from util.visualization import config
from util.visualization.builders import (
    geotiff_layers_from_links,
    images_from_links,
    parse_cmr_box,
    split_result_links,
)
from util.visualization.gibs import gibs_entries_from_tags, gibs_layers_from_entries
from util.visualization.specs import (
    FootprintLayer,
    GeoTiffLayer,
    GibsLayer,
    MapSpec,
    Series,
    VizSpec,
)

TIF = "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.tif"
PNG = "https://harmony.earthdata.nasa.gov/service-results/harmony-prod-staging/public/j/1/sst.png"


class TestSpecs:
    def test_geotiff_requires_https(self):
        with pytest.raises(ValidationError, match="https"):
            GeoTiffLayer(name="a", url="http://example.com/a.tif")

    def test_geotiff_localhost_only_when_allowed(self, monkeypatch):
        with pytest.raises(ValidationError):
            GeoTiffLayer(name="a", url="http://localhost:8765/sst.tif")
        monkeypatch.setenv("VIZ_ALLOW_LOCALHOST_HTTP", "true")
        assert GeoTiffLayer(name="a", url="http://localhost:8765/sst.tif").url.startswith("http://localhost")

    def test_geotiff_rejects_unknown_colormap_and_bad_range(self):
        with pytest.raises(ValidationError, match="colormap"):
            GeoTiffLayer(name="a", url=TIF, colormap="rainbow-ish")
        with pytest.raises(ValidationError, match="vmin"):
            GeoTiffLayer(name="a", url=TIF, vmin=5, vmax=5)

    @pytest.mark.parametrize("name", ["", "has space", "x" * 81, "quote'"])
    def test_layer_name_is_restricted(self, name):
        with pytest.raises(ValidationError):
            FootprintLayer(name=name, boxes=[[0, 0, 1, 1]])

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"layer": "Bad Layer"},
            {"layer": "OK", "date": "yesterday"},
            {"layer": "OK", "tile_matrix_set": "250m"},
        ],
    )
    def test_gibs_fields_are_validated(self, kwargs):
        with pytest.raises(ValidationError):
            GibsLayer(name="g", **kwargs)

    def test_gibs_max_zoom(self):
        assert GibsLayer(name="g", layer="X", tile_matrix_set="GoogleMapsCompatible_Level7").max_zoom == 7

    @pytest.mark.parametrize("box", [[0, 10, 1, 5], [0, -91, 1, 5], [200, 0, 1, 1]])
    def test_bounds_validation(self, box):
        with pytest.raises(ValidationError):
            FootprintLayer(name="f", boxes=[box])

    def test_antimeridian_box_is_allowed(self):
        assert FootprintLayer(name="f", boxes=[[170, -10, -170, 10]]).boxes == [[170, -10, -170, 10]]

    def test_duplicate_layer_names_rejected(self):
        with pytest.raises(ValidationError, match="duplicate"):
            MapSpec(title="t", layers=[GibsLayer(name="a", layer="X"), GibsLayer(name="a", layer="Y")])

    def test_initial_bounds_from_footprints(self):
        spec = MapSpec(
            title="t",
            layers=[FootprintLayer(name="f", boxes=[[0, 0, 10, 10], [-5, 2, 3, 20]])],
        )
        assert spec.initial_bounds() == [-5, 0, 10, 20]
        assert MapSpec(title="t", bounds=[1, 2, 3, 4]).initial_bounds() == [1, 2, 3, 4]

    def test_viz_shapes(self):
        with pytest.raises(ValidationError, match="images"):
            VizSpec(title="t", kind="image")
        with pytest.raises(ValidationError, match="columns not found"):
            VizSpec(title="t", kind="line", rows=[{"d": 1}], x="d", series=[Series(key="v")])
        VizSpec(title="t", kind="line", rows=[{"d": 1, "v": 2}], x="d", series=[Series(key="v")])
        VizSpec(title="t", kind="histogram", values=[1.0, 2.0])


class TestBuilders:
    def test_parse_cmr_box_reorders(self):
        assert parse_cmr_box("5.95 34.82 29.5 55.33") == [34.82, 5.95, 55.33, 29.5]

    def test_split_and_filter_links(self):
        groups = split_result_links([TIF, PNG, "https://x.org/a.nc", TIF + "?sig=1"])
        assert groups["geotiff"] == [TIF, TIF + "?sig=1"]
        assert groups["image"] == [PNG]
        assert groups["other"] == ["https://x.org/a.nc"]

    def test_geotiff_layers_first_visible_and_fit(self):
        layers = geotiff_layers_from_links([TIF, PNG, TIF.replace("sst", "sst2")], title="SST",
                                           scale=0.001, offset=298.15, units="K")
        assert [layer.visible for layer in layers] == [True, False]
        assert [layer.fit for layer in layers] == [True, False]
        assert layers[0].title == "SST" and layers[1].title == "SST (2)"
        assert layers[0].value_scale.scale == 0.001 and layers[0].value_scale.offset == 298.15

    def test_geotiff_layers_without_scale(self):
        assert geotiff_layers_from_links([TIF])[0].value_scale is None

    def test_images_from_links(self):
        assert [i.url for i in images_from_links([TIF, PNG])] == [PNG]


class TestGibs:
    ENTRIES = [
        {"product": "AIRS_Day", "title": "AIRS day", "format": "png", "geographic_resolution": "2km",
         "match": {"day_night_flag": "day"}},
        {"product": "AIRS_Night", "title": "AIRS night", "format": "png", "geographic_resolution": "2km",
         "match": {"day_night_flag": "night"}},
        {"product": "Odd", "geographic_resolution": "31km"},
        {"product": "MODIS_TC", "format": "jpeg", "geographic_resolution": "250m"},
    ]

    def test_entries_from_tags(self):
        tags = {"edsc.extra.serverless.gibs": {"data": self.ENTRIES + [{"title": "no product"}]}}
        assert len(gibs_entries_from_tags(tags)) == 4
        assert gibs_entries_from_tags({}) == []

    def test_layers_map_resolution_and_format(self):
        layers = gibs_layers_from_entries(self.ENTRIES, date="2024-06-15", max_layers=5)
        assert [g.layer for g in layers] == ["AIRS_Day", "AIRS_Night", "MODIS_TC"]  # 31km skipped
        assert layers[0].tile_matrix_set == "GoogleMapsCompatible_Level6" and layers[0].format == "png"
        assert layers[2].tile_matrix_set == "GoogleMapsCompatible_Level9" and layers[2].format == "jpg"
        assert [g.visible for g in layers] == [True, False, False]
        assert all(g.date == "2024-06-15" for g in layers)

    def test_day_night_filter(self):
        assert [g.layer for g in gibs_layers_from_entries(self.ENTRIES, day_night="night", max_layers=1)] == [
            "AIRS_Night"
        ]


class TestCsp:
    def test_unlisted_origins(self):
        allowed = ["https://a.org", "http://localhost:*"]
        assert config.unlisted_origins({"https://a.org", "https://b.org", "http://localhost:8765"}, allowed) == [
            "https://b.org"
        ]

    def test_env_extras(self, monkeypatch):
        monkeypatch.setenv("VIZ_EXTRA_CONNECT_DOMAINS", "https://data.example.org/, https://x.org")
        domains = config.map_csp_domains()
        assert "https://data.example.org" in domains["connect_domains"]
        assert "https://gibs.earthdata.nasa.gov" in domains["resource_domains"]
        assert len(domains["connect_domains"]) == len(set(domains["connect_domains"]))

    def test_harmony_results_are_covered_by_default(self):
        spec = MapSpec(title="t", layers=[GeoTiffLayer(name="a", url=TIF)])
        assert config.unlisted_origins(spec.data_origins(), config.map_csp_domains()["connect_domains"]) == []
