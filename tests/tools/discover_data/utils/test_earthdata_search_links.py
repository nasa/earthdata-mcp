"""Tests for Earthdata Search link utilities."""

from datetime import UTC, datetime

from models.tools.discover_data import SpatialConstraint, TemporalConstraint
from tools.discover_data.utils.earthdata_search_links import _earthdata_search_link


class TestEarthdataSearchLink:
    """Tests for _earthdata_search_link helper."""

    def test_includes_concept_id_as_p_param(self):
        """Link URL should filter granules by the given concept ID."""
        link = _earthdata_search_link("C1234-PROV")
        assert "p=C1234-PROV" in link["url"]

    def test_name_is_earthdata_search(self):
        """Name field should identify the tool."""
        link = _earthdata_search_link("C1234-PROV")
        assert link["name"] == "NASA Earthdata Search"

    def test_topic_is_data_access(self):
        """Topic field should be 'Data access'."""
        link = _earthdata_search_link("C1234-PROV")
        assert link["topic"] == "Data analysis and visualization"

    def test_url_starts_with_earthdata_search_base(self):
        """URL should use the Earthdata Search base domain."""
        link = _earthdata_search_link("C9999-PROV")
        assert link["url"].startswith("https://search.earthdata.nasa.gov")

    def test_adds_qt_for_both_temporal_bounds(self):
        """qt= should contain both start and end when both are present."""
        temporal = TemporalConstraint(
            start_date=datetime(2026, 3, 1, tzinfo=UTC),
            end_date=datetime(2026, 3, 6, tzinfo=UTC),
        )
        link = _earthdata_search_link("C1-P", temporal=temporal)
        assert "qt=" in link["url"]
        assert "2026-03-01T00%3A00%3A00.000Z" in link["url"]
        assert "2026-03-06T00%3A00%3A00.999Z" in link["url"]

    def test_adds_qt_with_empty_end_when_only_start(self):
        """qt= value should have trailing comma (open end) when only start_date present."""
        temporal = TemporalConstraint(start_date=datetime(2026, 3, 1, tzinfo=UTC))
        link = _earthdata_search_link("C1-P", temporal=temporal)
        assert "qt=" in link["url"]
        assert "2026-03-01" in link["url"]

    def test_omits_qt_when_no_temporal_and_no_collection_end(self):
        """qt= should be absent when no temporal constraint and no collection_end_date."""
        link = _earthdata_search_link("C1-P", temporal=None)
        assert "qt=" not in link["url"]

    def test_omits_qt_when_no_temporal_even_with_collection_end_date(self):
        """qt= should remain absent when no query temporal is present."""
        end = datetime(2020, 12, 31, tzinfo=UTC)
        link = _earthdata_search_link("C1-P", temporal=None, collection_end_date=end)
        assert "qt=" not in link["url"]

    def test_query_temporal_takes_priority_over_collection_end_date(self):
        """Explicit query temporal should take precedence over collection_end_date."""
        temporal = TemporalConstraint(
            start_date=datetime(2010, 1, 1, tzinfo=UTC),
            end_date=datetime(2015, 6, 30, tzinfo=UTC),
        )
        end = datetime(2020, 12, 31, tzinfo=UTC)
        link = _earthdata_search_link("C1-P", temporal=temporal, collection_end_date=end)
        assert "2010-01-01" in link["url"]
        assert "2015-06-30" in link["url"]
        assert "2020-12-31" not in link["url"]

    def test_adds_sb_from_spatial_wkt(self):
        """sb[0]= should contain the bounding box derived from the WKT geometry."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))")
        link = _earthdata_search_link("C1-P", spatial=spatial)
        assert "sb[0]=" in link["url"]
        assert "-10.0" in link["url"]
        assert "60.0" in link["url"]

    def test_omits_sb_when_no_spatial(self):
        """sb[0]= should be absent when no spatial constraint is provided."""
        link = _earthdata_search_link("C1-P", spatial=None)
        assert "sb" not in link["url"]

    def test_adds_arctic_projection_for_arctic_spatial(self):
        """Should include lat=90, EPSG:3413, zoom=2 for arctic spatial extents."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 65, 10 65, 10 80, 0 80, 0 65))")
        link = _earthdata_search_link("C1-P", spatial=spatial)
        assert "lat=90" in link["url"]
        assert "EPSG" in link["url"]
        assert "3413" in link["url"]
        assert "zoom=2" in link["url"]

    def test_adds_antarctic_projection_for_antarctic_spatial(self):
        """Should include lat=-90, EPSG:3031, zoom=2 for antarctic spatial extents."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((0 -80, 10 -80, 10 -65, 0 -65, 0 -80))")
        link = _earthdata_search_link("C1-P", spatial=spatial)
        assert "lat=-90" in link["url"]
        assert "3031" in link["url"]
        assert "zoom=2" in link["url"]

    def test_omits_projection_param_for_geographic_spatial(self):
        """Should not add projection= for mid-latitude geographic extents."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 50, -10 50, -10 20))")
        link = _earthdata_search_link("C1-P", spatial=spatial)
        assert "projection=" not in link["url"]

    def test_adds_lat_long_zoom_for_geographic_spatial(self):
        """Should include lat=, long=, zoom= centred on bbox for geographic projection."""
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 50, -10 50, -10 20))")
        link = _earthdata_search_link("C1-P", spatial=spatial)
        # bbox is west=-10, south=20, east=30, north=50 → center (35, 10)
        assert "lat=35.0" in link["url"]
        assert "long=10.0" in link["url"]
        assert "zoom=" in link["url"]

    def test_omits_lat_long_zoom_when_no_spatial(self):
        """lat/long/zoom should be absent when no spatial constraint is provided."""
        link = _earthdata_search_link("C1-P", spatial=None)
        assert "lat=" not in link["url"]
        assert "long=" not in link["url"]
        assert "zoom=" not in link["url"]
