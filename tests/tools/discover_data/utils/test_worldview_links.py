"""Tests for Worldview and GIBS link utilities."""

from datetime import UTC, datetime
from typing import ClassVar

from models.tools.discover_data import SpatialConstraint, TemporalConstraint
from tools.discover_data.utils.worldview_links import (
    _all_gibs_layers,
    _best_gibs_layer,
    _gibs_entry_matches_temporal,
    _preferred_projection,
    _worldview_link,
)


class TestPreferredProjection:
    """Tests for _preferred_projection helper."""

    def test_returns_geographic_when_no_spatial(self):
        """Should return geographic when spatial is None."""
        assert _preferred_projection(None) == "geographic"

    def test_returns_geographic_when_no_wkt(self):
        """Should return geographic when spatial has no wkt_geometry."""
        assert _preferred_projection(SpatialConstraint()) == "geographic"

    def test_returns_geographic_for_mid_latitude_bbox(self):
        """A mid-latitude polygon should map to geographic projection."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 50, -10 50, -10 20))")
        assert _preferred_projection(spatial) == "geographic"

    def test_returns_arctic_when_entire_bbox_above_threshold(self):
        """Min latitude >= 60 should select arctic projection."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 65, 30 65, 30 80, -10 80, -10 65))")
        assert _preferred_projection(spatial) == "arctic"

    def test_returns_arctic_exactly_at_threshold(self):
        """Min latitude exactly at 60.0 should trigger arctic."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 60, 10 60, 10 70, 0 70, 0 60))")
        assert _preferred_projection(spatial) == "arctic"

    def test_returns_antarctic_when_entire_bbox_below_threshold(self):
        """Max latitude <= -60 should select antarctic projection."""
        spatial = SpatialConstraint(
            wkt_geometry="POLYGON((-10 -80, 30 -80, 30 -65, -10 -65, -10 -80))"
        )
        assert _preferred_projection(spatial) == "antarctic"

    def test_returns_antarctic_exactly_at_threshold(self):
        """Max latitude exactly at -60.0 should trigger antarctic."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 -70, 10 -70, 10 -60, 0 -60, 0 -70))")
        assert _preferred_projection(spatial) == "antarctic"

    def test_returns_geographic_for_cross_equator_bbox(self):
        """A bbox spanning both hemispheres should remain geographic."""
        spatial = SpatialConstraint(
            wkt_geometry="POLYGON((-10 -30, 30 -30, 30 30, -10 30, -10 -30))"
        )
        assert _preferred_projection(spatial) == "geographic"


# ---------------------------------------------------------------------------
# _best_gibs_layer
# ---------------------------------------------------------------------------


class TestBestGibsLayer:
    """Tests for _best_gibs_layer helper."""

    _GEO_LAYER: ClassVar[dict] = {
        "product": "MODIS_Terra_Geo",
        "geographic": True,
        "arctic": False,
        "antarctic": False,
    }
    _ARCTIC_LAYER: ClassVar[dict] = {
        "product": "MODIS_Terra_Arctic",
        "geographic": False,
        "arctic": True,
        "antarctic": False,
    }
    _ANTARCTIC_LAYER: ClassVar[dict] = {
        "product": "MODIS_Terra_Antarctic",
        "geographic": False,
        "arctic": False,
        "antarctic": True,
    }

    def _tags(self, layers: list) -> dict:
        return {"edsc.extra.serverless.gibs": {"data": layers}}

    def test_returns_none_for_empty_tags(self):
        """Should return None when tags dict is empty."""
        assert _best_gibs_layer({}, None) is None

    def test_returns_none_when_gibs_key_absent(self):
        """Should return None when edsc.extra.serverless.gibs key is missing."""
        assert _best_gibs_layer({"other.tag": {}}, None) is None

    def test_returns_none_when_data_is_empty(self):
        """Should return None when data array is empty."""
        assert _best_gibs_layer(self._tags([]), None) is None

    def test_picks_geographic_layer_for_mid_latitude_spatial(self):
        """Should return the geographic layer product for a mid-latitude extent."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 50, -10 50, -10 20))")
        tags = self._tags([self._GEO_LAYER])
        assert _best_gibs_layer(tags, spatial) == "MODIS_Terra_Geo"

    def test_picks_geographic_layer_when_no_spatial(self):
        """Should return the geographic layer when spatial is None."""
        tags = self._tags([self._GEO_LAYER])
        assert _best_gibs_layer(tags, None) == "MODIS_Terra_Geo"

    def test_picks_arctic_layer_for_arctic_spatial(self):
        """Should prefer arctic layer when spatial is entirely above 60N."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        tags = self._tags([self._GEO_LAYER, self._ARCTIC_LAYER])
        assert _best_gibs_layer(tags, spatial) == "MODIS_Terra_Arctic"

    def test_falls_back_to_geographic_when_no_arctic_layer(self):
        """Should fall back to geographic when arctic spatial has no arctic layer."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        tags = self._tags([self._GEO_LAYER])
        assert _best_gibs_layer(tags, spatial) == "MODIS_Terra_Geo"

    def test_picks_antarctic_layer_for_antarctic_spatial(self):
        """Should prefer antarctic layer when spatial is entirely below -60S."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 -80, 10 -80, 10 -65, 0 -65, 0 -80))")
        tags = self._tags([self._GEO_LAYER, self._ANTARCTIC_LAYER])
        assert _best_gibs_layer(tags, spatial) == "MODIS_Terra_Antarctic"

    def test_falls_back_to_geographic_when_no_antarctic_layer(self):
        """Should fall back to geographic when antarctic spatial has no antarctic layer."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 -80, 10 -80, 10 -65, 0 -65, 0 -80))")
        tags = self._tags([self._GEO_LAYER])
        assert _best_gibs_layer(tags, spatial) == "MODIS_Terra_Geo"

    def test_skips_layers_where_projection_field_is_false(self):
        """Should not return a layer whose preferred projection field is False."""
        layer_geo_false = {
            "product": "WrongLayer",
            "geographic": False,
            "arctic": False,
            "antarctic": False,
        }
        tags = self._tags([layer_geo_false])
        assert _best_gibs_layer(tags, None) is None

    def test_returns_first_matching_layer(self):
        """Should return the product of the first geographic=True entry."""
        layer_a = {"product": "LayerA", "geographic": True, "arctic": False, "antarctic": False}
        layer_b = {"product": "LayerB", "geographic": True, "arctic": False, "antarctic": False}
        assert _best_gibs_layer(self._tags([layer_a, layer_b]), None) == "LayerA"


# ---------------------------------------------------------------------------
# _all_gibs_layers
# ---------------------------------------------------------------------------


class TestAllGibsLayers:
    """Tests for _all_gibs_layers helper."""

    _GEO_LAYER_A: ClassVar[dict] = {
        "product": "LayerGeoA",
        "geographic": True,
        "arctic": False,
        "antarctic": False,
    }
    _GEO_LAYER_B: ClassVar[dict] = {
        "product": "LayerGeoB",
        "geographic": True,
        "arctic": False,
        "antarctic": False,
    }
    _ARCTIC_LAYER: ClassVar[dict] = {
        "product": "LayerArctic",
        "geographic": False,
        "arctic": True,
        "antarctic": False,
    }
    _ANTARCTIC_LAYER: ClassVar[dict] = {
        "product": "LayerAntarctic",
        "geographic": False,
        "arctic": False,
        "antarctic": True,
    }

    def _tags(self, layers: list) -> dict:
        return {"edsc.extra.serverless.gibs": {"data": layers}}

    def test_returns_empty_list_when_no_tags(self):
        """Should return empty list when tags is empty."""
        assert not _all_gibs_layers({}, None)

    def test_returns_all_geographic_layers(self):
        """Should return all geographic layers when spatial is None."""
        tags = self._tags([self._GEO_LAYER_A, self._GEO_LAYER_B])
        result = _all_gibs_layers(tags, None)
        assert result == ["LayerGeoA", "LayerGeoB"]

    def test_arctic_layers_precede_geographic_for_arctic_spatial(self):
        """Arctic layers should come before geographic fallback layers for polar extents."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        tags = self._tags([self._GEO_LAYER_A, self._ARCTIC_LAYER])
        result = _all_gibs_layers(tags, spatial)
        assert result[0] == "LayerArctic"
        assert "LayerGeoA" in result

    def test_no_duplicates_across_projections(self):
        """A layer matching both arctic and geographic should appear only once."""
        dual_layer = {
            "product": "DualLayer",
            "geographic": True,
            "arctic": True,
            "antarctic": False,
        }
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        tags = self._tags([dual_layer])
        result = _all_gibs_layers(tags, spatial)
        assert result.count("DualLayer") == 1

    def test_returns_empty_when_no_layers_match_projection(self):
        """Should return empty list when no layer matches the preferred projection."""
        tags = self._tags([self._ANTARCTIC_LAYER])
        result = _all_gibs_layers(tags, None)  # geographic preferred, no geo layers
        assert not result

    def test_single_layer_consistent_with_best_gibs_layer(self):
        """First element should match what _best_gibs_layer returns."""
        tags = self._tags([self._GEO_LAYER_A, self._GEO_LAYER_B])
        assert _all_gibs_layers(tags, None)[0] == _best_gibs_layer(tags, None)

    def test_excludes_layer_whose_match_window_is_entirely_before_query(self):
        """Layer valid only before the query range should be excluded."""
        layer = {
            "product": "OldLayer",
            "geographic": True,
            "match": {"time_start": ">=2000-01-01T00:00:00Z", "time_end": "<=2005-12-31T23:59:59Z"},
        }
        temporal = TemporalConstraint(
            start_date=datetime(2010, 1, 1, tzinfo=UTC),
            end_date=datetime(2015, 1, 1, tzinfo=UTC),
        )
        result = _all_gibs_layers(self._tags([layer]), None, temporal=temporal)
        assert not result

    def test_excludes_layer_whose_match_window_is_entirely_after_query(self):
        """Layer valid only after the query range should be excluded."""
        layer = {
            "product": "FutureLayer",
            "geographic": True,
            "match": {"time_start": ">=2030-01-01T00:00:00Z"},
        }
        temporal = TemporalConstraint(
            start_date=datetime(2010, 1, 1, tzinfo=UTC),
            end_date=datetime(2015, 1, 1, tzinfo=UTC),
        )
        result = _all_gibs_layers(self._tags([layer]), None, temporal=temporal)
        assert not result

    def test_includes_layer_whose_match_window_overlaps_query(self):
        """Layer whose valid window overlaps the query range should be included."""
        layer = {
            "product": "ActiveLayer",
            "geographic": True,
            "match": {"time_start": ">=2010-06-01T00:00:00Z", "time_end": "<=2020-01-01T00:00:00Z"},
        }
        temporal = TemporalConstraint(
            start_date=datetime(2012, 1, 1, tzinfo=UTC),
            end_date=datetime(2014, 1, 1, tzinfo=UTC),
        )
        result = _all_gibs_layers(self._tags([layer]), None, temporal=temporal)
        assert result == ["ActiveLayer"]

    def test_includes_layer_with_no_match_key_regardless_of_temporal(self):
        """Layer with no match constraint should always be included."""
        temporal = TemporalConstraint(
            start_date=datetime(2010, 1, 1, tzinfo=UTC),
            end_date=datetime(2015, 1, 1, tzinfo=UTC),
        )
        result = _all_gibs_layers(self._tags([self._GEO_LAYER_A]), None, temporal=temporal)
        assert result == ["LayerGeoA"]

    def test_uses_collection_end_date_as_point_filter_when_no_temporal(self):
        """collection_end_date should act as a point-in-time filter when no query temporal set."""
        old_layer = {
            "product": "OldLayer",
            "geographic": True,
            "match": {"time_start": ">=2000-01-01T00:00:00Z", "time_end": "<=2005-12-31T23:59:59Z"},
        }
        new_layer = {
            "product": "NewLayer",
            "geographic": True,
            "match": {"time_start": ">=2006-01-01T00:00:00Z", "time_end": "<=2015-12-31T23:59:59Z"},
        }
        collection_end = datetime(2011, 6, 15, tzinfo=UTC)
        result = _all_gibs_layers(
            self._tags([old_layer, new_layer]),
            None,
            collection_end_date=collection_end,
        )
        assert result == ["NewLayer"]

    def test_returns_all_layers_when_no_temporal_and_no_collection_end(self):
        """Should include all matching-projection layers when no temporal context is available."""
        timed_layer = {
            "product": "TimedLayer",
            "geographic": True,
            "match": {"time_start": ">=2000-01-01T00:00:00Z", "time_end": "<=2005-12-31T23:59:59Z"},
        }
        result = _all_gibs_layers(self._tags([timed_layer]), None)
        assert result == ["TimedLayer"]


# ---------------------------------------------------------------------------
# _gibs_entry_matches_temporal
# ---------------------------------------------------------------------------


class TestGibsEntryMatchesTemporal:
    """Tests for _gibs_entry_matches_temporal helper."""

    def test_no_match_key_always_valid(self):
        """Entry without a match key is valid for any temporal context."""
        assert _gibs_entry_matches_temporal({"product": "X"}, None, None) is True

    def test_empty_match_always_valid(self):
        """Entry with an empty match dict is valid for any temporal context."""
        assert _gibs_entry_matches_temporal({"product": "X", "match": {}}, None, None) is True

    def test_no_temporal_context_always_valid(self):
        """Without temporal or collection_end_date all entries are valid."""
        entry = {
            "product": "X",
            "match": {"time_start": ">=2000-01-01T00:00:00Z", "time_end": "<=2005-12-31T23:59:59Z"},
        }
        assert _gibs_entry_matches_temporal(entry, None, None) is True

    def test_query_range_overlaps_layer_window(self):
        """Should return True when query range overlaps the layer's valid window."""
        entry = {
            "match": {"time_start": ">=2010-01-01T00:00:00Z", "time_end": "<=2020-12-31T23:59:59Z"}
        }
        temporal = TemporalConstraint(
            start_date=datetime(2012, 6, 1, tzinfo=UTC),
            end_date=datetime(2013, 6, 1, tzinfo=UTC),
        )
        assert _gibs_entry_matches_temporal(entry, temporal, None) is True

    def test_query_range_entirely_before_layer_window(self):
        """Should return False when query ends before the layer starts."""
        entry = {"match": {"time_start": ">=2015-01-01T00:00:00Z"}}
        temporal = TemporalConstraint(
            start_date=datetime(2010, 1, 1, tzinfo=UTC),
            end_date=datetime(2012, 1, 1, tzinfo=UTC),
        )
        assert _gibs_entry_matches_temporal(entry, temporal, None) is False

    def test_query_range_entirely_after_layer_window(self):
        """Should return False when query starts after the layer ends."""
        entry = {"match": {"time_end": "<=2005-12-31T23:59:59Z"}}
        temporal = TemporalConstraint(
            start_date=datetime(2010, 1, 1, tzinfo=UTC),
            end_date=datetime(2015, 1, 1, tzinfo=UTC),
        )
        assert _gibs_entry_matches_temporal(entry, temporal, None) is False

    def test_open_ended_layer_always_valid_for_query_after_start(self):
        """Layer with only time_start should be valid for any query after that date."""
        entry = {"match": {"time_start": ">=2012-07-02T00:00:00Z"}}
        temporal = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
        assert _gibs_entry_matches_temporal(entry, temporal, None) is True

    def test_collection_end_date_within_layer_window(self):
        """collection_end_date falling within the layer window → valid."""
        entry = {
            "match": {"time_start": ">=2010-01-01T00:00:00Z", "time_end": "<=2015-12-31T23:59:59Z"}
        }
        assert _gibs_entry_matches_temporal(entry, None, datetime(2012, 6, 1, tzinfo=UTC)) is True

    def test_collection_end_date_outside_layer_window(self):
        """collection_end_date outside the layer window → invalid."""
        entry = {
            "match": {"time_start": ">=2010-01-01T00:00:00Z", "time_end": "<=2015-12-31T23:59:59Z"}
        }
        assert _gibs_entry_matches_temporal(entry, None, datetime(2020, 1, 1, tzinfo=UTC)) is False


class TestWorldviewLink:
    """Tests for _worldview_link helper."""

    def test_includes_layer_in_url(self):
        """URL should contain the GIBS layer in the l= parameter."""
        link = _worldview_link(["MODIS_Terra_TrueColor"], None)
        assert "MODIS_Terra_TrueColor" in link["url"]

    def test_appends_blue_marble_base_layer(self):
        """BlueMarble_NextGeneration should always be appended to the layers list."""
        link = _worldview_link(["MODIS_Terra_TrueColor"], None)
        assert "BlueMarble_NextGeneration" in link["url"]

    def test_name_is_nasa_worldview(self):
        """Name field should be 'NASA Worldview'."""
        link = _worldview_link(["MODIS_Terra_TrueColor"], None)
        assert link["name"] == "NASA Worldview"

    def test_topic_is_visualization(self):
        """Topic field should mention visualization."""
        link = _worldview_link(["MODIS_Terra_TrueColor"], None)
        assert "visualization" in link["topic"].lower()

    def test_adds_t_param_when_temporal_has_start_date(self):
        """Should include t= in Worldview's dash-T format when a start_date is available."""
        temporal = TemporalConstraint(start_date=datetime(2021, 6, 15, tzinfo=UTC))
        link = _worldview_link(["MODIS_Terra_TrueColor"], temporal)
        assert "t=" in link["url"]
        assert "2021-06-15-T" in link["url"]

    def test_omits_t_param_when_no_temporal(self):
        """Should not include t= when temporal is None."""
        link = _worldview_link(["MODIS_Terra_TrueColor"], None)
        assert "t=" not in link["url"]

    def test_omits_t_param_when_temporal_has_no_start_date(self):
        """Should not include t= when temporal exists but start_date is absent and no collection end date."""
        temporal = TemporalConstraint(end_date=datetime(2021, 6, 15, tzinfo=UTC))
        link = _worldview_link(["MODIS_Terra_TrueColor"], temporal)
        assert "t=" not in link["url"]

    def test_uses_collection_end_date_as_t_fallback_when_no_query_start(self):
        """Should use collection_end_date for t= when query has no start_date."""
        end = datetime(2015, 12, 31, tzinfo=UTC)
        link = _worldview_link(["SomeLayer"], None, collection_end_date=end)
        assert "t=" in link["url"]
        assert "2015-12-31-T" in link["url"]

    def test_query_start_date_takes_priority_over_collection_end_date(self):
        """temporal.start_date should take precedence over collection_end_date for t=."""
        temporal = TemporalConstraint(start_date=datetime(2010, 1, 1, tzinfo=UTC))
        end = datetime(2015, 12, 31, tzinfo=UTC)
        link = _worldview_link(["SomeLayer"], temporal, collection_end_date=end)
        assert "2010-01-01-T" in link["url"]
        assert "2015-12-31" not in link["url"]

    def test_omits_t_when_no_query_start_and_no_collection_end(self):
        """Should omit t= entirely when neither query start_date nor collection_end_date is set."""
        link = _worldview_link(["SomeLayer"], None, collection_end_date=None)
        assert "t=" not in link["url"]

    def test_multiple_layers_all_appear_in_url(self):
        """First layer is visible; subsequent layers are marked (hidden); BlueMarble_NextGeneration is last."""
        link = _worldview_link(["LayerA", "LayerB", "LayerC"], None)
        assert "LayerA" in link["url"]
        assert "LayerB(hidden)" in link["url"]
        assert "LayerC(hidden)" in link["url"]
        # First layer must not be hidden
        assert "LayerA(hidden)" not in link["url"]
        # BlueMarble_NextGeneration must come last
        assert link["url"].index("BlueMarble_NextGeneration") > link["url"].index("LayerC")

    def test_adds_v_viewport_when_spatial_provided(self):
        """v= should contain the bounding box for geographic spatial extents."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))")
        link = _worldview_link(["MODIS_Terra_TrueColor"], None, spatial)
        assert "v=" in link["url"]
        assert "-10.0" in link["url"]

    def test_omits_v_when_no_spatial(self):
        """v= should be absent when no spatial constraint is provided."""
        link = _worldview_link(["MODIS_Terra_TrueColor"], None, None)
        assert "v=" not in link["url"]

    def test_omits_v_for_arctic_spatial(self):
        """v= should be absent for arctic extents — lat/lon bbox is invalid in polar projection."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        link = _worldview_link(["ArcticLayer"], None, spatial)
        assert "v=" not in link["url"]

    def test_omits_v_for_antarctic_spatial(self):
        """v= should be absent for antarctic extents — lat/lon bbox is invalid in polar projection."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 -80, 10 -80, 10 -65, 0 -65, 0 -80))")
        link = _worldview_link(["AntarcticLayer"], None, spatial)
        assert "v=" not in link["url"]

    def test_url_starts_with_worldview_base(self):
        """URL should use the Worldview base domain."""
        link = _worldview_link(["SomeLayer"], None)
        assert link["url"].startswith("https://worldview.earthdata.nasa.gov")

    def test_adds_arctic_projection_for_arctic_spatial(self):
        """p=arctic should be set when the spatial extent is above the arctic threshold."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        link = _worldview_link(["ArcticLayer"], None, spatial)
        assert "p=arctic" in link["url"]

    def test_adds_antarctic_projection_for_antarctic_spatial(self):
        """p=antarctic should be set when the spatial extent is below the antarctic threshold."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 -80, 10 -80, 10 -65, 0 -65, 0 -80))")
        link = _worldview_link(["AntarcticLayer"], None, spatial)
        assert "p=antarctic" in link["url"]

    def test_omits_p_for_geographic_spatial(self):
        """p= should be absent for mid-latitude geographic extents (geographic is the default)."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 50, -10 50, -10 20))")
        link = _worldview_link(["SomeLayer"], None, spatial)
        assert "p=" not in link["url"]

    def test_omits_p_when_no_spatial(self):
        """p= should be absent when no spatial constraint is provided."""
        link = _worldview_link(["SomeLayer"], None, None)
        assert "p=" not in link["url"]
