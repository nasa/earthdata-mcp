"""Tests for tool association enrichment."""

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from models.tools.discover_data import CollectionMatch, SpatialConstraint, TemporalConstraint
from tools.discover_data.utils.tool_associations import (
    TOOL_ASSOC_CACHE_TTL,
    ToolAssociationError,
    _all_gibs_layers,
    _bbox_from_wkt,
    _best_gibs_layer,
    _build_exploration_links,
    _cache_key,
    _earthdata_search_link,
    _expand_url_template,
    _fetch_tool_associations,
    _gibs_entry_matches_temporal,
    _preferred_projection,
    _map_center_zoom,
    _prioritize_tools,
    _resolve_tool_url,
    _resolve_value,
    _round_bbox,
    _worldview_link,
    enrich_with_tool_associations,
)


def _make_collection(concept_id: str) -> CollectionMatch:
    return CollectionMatch(
        concept_id=concept_id,
        title=f"Title {concept_id}",
        similarity_score=0.9,
        match_type="direct",
        matched_attribute="title",
    )


def _make_cache(*, hits: dict | None = None):
    """Return a mock cache client with controllable get/set behaviour."""
    cache = MagicMock()
    cache.get.side_effect = lambda key: (hits or {}).get(key)
    cache.set.return_value = None
    return cache


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------


class TestCacheKey:
    """Tests for _cache_key helper."""

    def test_includes_concept_id_verbatim(self):
        """Cache key should contain the raw concept ID for traceability."""
        key = _cache_key("C1234-PROVIDER")
        assert "C1234-PROVIDER" in key

    def test_includes_tool_associations_namespace(self):
        """Cache key should be namespaced to avoid collisions with other caches."""
        key = _cache_key("C1234-PROVIDER")
        assert key.startswith("tool_associations:")

    def test_same_concept_id_produces_same_key(self):
        """The same concept ID must always produce the same cache key."""
        assert _cache_key("C1234-PROVIDER") == _cache_key("C1234-PROVIDER")

    def test_different_concept_ids_produce_different_keys(self):
        """Different concept IDs must produce different cache keys."""
        assert _cache_key("C1234-PROVIDER") != _cache_key("C9999-OTHER")

    def test_hash_matches_sha256_of_concept_id(self):
        """The hash segment should be the SHA-256 of the concept ID."""
        concept_id = "C1234-PROVIDER"
        expected_hash = hashlib.sha256(concept_id.encode()).hexdigest()
        assert expected_hash in _cache_key(concept_id)


# ---------------------------------------------------------------------------
# _fetch_tool_associations
# ---------------------------------------------------------------------------


class TestFetchToolAssociations:
    """Tests for _fetch_tool_associations."""

    def test_returns_empty_tools_when_no_tools_in_associations(self, monkeypatch):
        """Should return empty tools list when collection has no tool associations."""
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_associations",
            lambda concept_id: {"variables": ["V1-P"]},  # tools key absent
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_collection_tags",
            lambda concept_id: {},
        )

        result = _fetch_tool_associations("C1234-PROVIDER")

        assert result["tools"] == []
        assert result["tags"] == {}

    def test_returns_empty_tools_when_tools_key_is_empty(self, monkeypatch):
        """Should return empty tools list when tools list is explicitly empty."""
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_associations",
            lambda concept_id: {"tools": []},
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_collection_tags",
            lambda concept_id: {},
        )

        result = _fetch_tool_associations("C1234-PROVIDER")

        assert result["tools"] == []

    def test_calls_fetch_tool_metadata_with_tool_ids(self, monkeypatch):
        """Should forward tool IDs to fetch_tool_metadata."""
        tool_ids = ["TL1-PROV", "TL2-PROV"]
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_associations",
            lambda concept_id: {"tools": tool_ids},
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_collection_tags",
            lambda concept_id: {},
        )
        fetch_metadata_calls = []
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_tool_metadata",
            lambda ids: fetch_metadata_calls.append(ids) or [],
        )

        _fetch_tool_associations("C1234-PROVIDER")

        assert fetch_metadata_calls == [tool_ids]

    def test_returns_raw_tool_dicts_from_fetch_tool_metadata(self, monkeypatch):
        """Should return the raw template dicts from fetch_tool_metadata in tools key."""
        tools = [
            {
                "name": "Giovanni",
                "url_template": "https://giovanni.example.com{?starttime}",
                "query_inputs": [
                    {
                        "value_name": "starttime",
                        "value_type": "https://schema.org/startDate",
                        "required": True,
                    }
                ],
            }
        ]
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_associations",
            lambda concept_id: {"tools": ["TL1-PROV"]},
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_collection_tags",
            lambda concept_id: {},
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_tool_metadata",
            lambda ids: tools,
        )

        result = _fetch_tool_associations("C1234-PROVIDER")

        assert result["tools"] == tools

    def test_returns_tags_from_fetch_collection_tags(self, monkeypatch):
        """Should include tags returned by fetch_collection_tags in result."""
        tags = {
            "edsc.extra.serverless.gibs": {"data": [{"product": "MODIS_Terra", "geographic": True}]}
        }
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_associations",
            lambda concept_id: {},
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_collection_tags",
            lambda concept_id: tags,
        )

        result = _fetch_tool_associations("C1234-PROVIDER")

        assert result["tags"] == tags

    def test_skips_fetch_tool_metadata_when_no_tool_ids(self, monkeypatch):
        """Should not call fetch_tool_metadata at all when there are no tool IDs."""
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_associations",
            lambda concept_id: {},
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_collection_tags",
            lambda concept_id: {},
        )
        metadata_called = []
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.fetch_tool_metadata",
            lambda ids: metadata_called.append(ids) or [],
        )

        _fetch_tool_associations("C1234-PROVIDER")

        assert not metadata_called


# ---------------------------------------------------------------------------
# enrich_with_tool_associations
# ---------------------------------------------------------------------------


class TestEnrichWithToolAssociations:
    """Tests for enrich_with_tool_associations."""

    def test_returns_empty_list_unchanged(self, monkeypatch):
        """Should return [] without hitting cache or CMR."""
        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )

        result = enrich_with_tool_associations([])

        assert result == []
        cache.get.assert_not_called()
        cache.set.assert_not_called()

    def test_uses_cached_raw_templates_and_resolves_url(self, monkeypatch):
        """Should read raw templates from cache and return resolved {name, url} dicts."""
        collection = _make_collection("C1-P")
        temporal = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
        # Cache stores raw templates (context-independent)
        raw_tools = [
            {
                "name": "Tool A",
                "url_template": "https://tool-a.example.com{?starttime}",
                "query_inputs": [
                    {
                        "value_name": "starttime",
                        "value_type": "https://schema.org/startDate",
                        "required": True,
                    }
                ],
            }
        ]
        key = _cache_key("C1-P")

        cache = _make_cache(hits={key: {"tools": raw_tools, "tags": {}}})
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        fetch_called = []
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: fetch_called.append(cid) or {"tools": [], "tags": {}},
        )

        result = enrich_with_tool_associations([collection], temporal=temporal)

        # Earthdata Search is always first; Tool A follows with starttime
        assert len(result[0].exploration_links) == 2
        assert result[0].exploration_links[0]["name"] == "NASA Earthdata Search"
        assert result[0].exploration_links[1]["name"] == "Tool A"
        assert "starttime=" in result[0].exploration_links[1]["url"]
        assert not fetch_called  # cache hit, CMR not called

    def test_fetches_from_cmr_on_cache_miss_and_resolves(self, monkeypatch):
        """Should fetch raw templates from CMR, cache them, and return resolved {name, url} dicts."""
        collection = _make_collection("C1-P")
        # Tool with a static URL (no query inputs) — resolves unchanged
        raw_tools = [
            {
                "name": "Tool B",
                "url_template": "https://tool-b.example.com/viewer",
                "query_inputs": [],
            }
        ]

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: {"tools": raw_tools, "tags": {}},
        )

        result = enrich_with_tool_associations([collection])

        # Earthdata Search is always first; Tool B follows
        assert len(result[0].exploration_links) == 2
        assert result[0].exploration_links[0]["name"] == "NASA Earthdata Search"
        assert result[0].exploration_links[1] == {
            "name": "Tool B",
            "url": "https://tool-b.example.com/viewer",
            "topic": None,
        }

        # Cache should store raw templates and tags, not resolved URLs
        cache.set.assert_called_once()
        call_args = cache.set.call_args
        assert call_args[0][0] == _cache_key("C1-P")
        assert call_args[0][1]["tools"] == raw_tools
        assert call_args[0][1]["tags"] == {}
        assert call_args[1]["ttl"] == TOOL_ASSOC_CACHE_TTL

    def test_sets_empty_list_for_collection_with_no_tools(self, monkeypatch):
        """Collections with no CMR tools should receive an empty exploration_links list."""
        collection = _make_collection("C1-P")

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: {"tools": [], "tags": {}},
        )

        result = enrich_with_tool_associations([collection])

        # Even with no CMR tools, the guaranteed Earthdata Search link is present
        assert len(result[0].exploration_links) == 1
        assert result[0].exploration_links[0]["name"] == "NASA Earthdata Search"
        assert "C1-P" in result[0].exploration_links[0]["url"]

    def test_returns_same_list_object(self, monkeypatch):
        """Should return the original list (mutated in-place), not a new list."""
        collections = [_make_collection("C1-P")]
        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: {"tools": [], "tags": {}},
        )

        result = enrich_with_tool_associations(collections)

        assert result is collections

    def test_handles_mixed_cache_hit_and_miss(self, monkeypatch):
        """Some collections cached, others not — both get resolved {name, url} dicts."""
        c1 = _make_collection("C1-P")
        c2 = _make_collection("C2-P")

        # Static URLs (no query inputs) so resolved URL == url_template
        cached_raw = [
            {
                "name": "Cached Tool",
                "url_template": "https://cached.example.com",
                "query_inputs": [],
            }
        ]
        fetched_raw = [
            {
                "name": "Fetched Tool",
                "url_template": "https://fetched.example.com",
                "query_inputs": [],
            }
        ]

        cache = _make_cache(hits={_cache_key("C1-P"): {"tools": cached_raw, "tags": {}}})
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: {"tools": fetched_raw, "tags": {}},
        )

        result = enrich_with_tool_associations([c1, c2])

        c1_result = next(c for c in result if c.concept_id == "C1-P")
        c2_result = next(c for c in result if c.concept_id == "C2-P")
        # Index [0] is always Earthdata Search; CMR tools start at [1]
        assert c1_result.exploration_links[0]["name"] == "NASA Earthdata Search"
        assert c1_result.exploration_links[1]["name"] == "Cached Tool"
        assert c1_result.exploration_links[1]["url"] == "https://cached.example.com"
        assert c2_result.exploration_links[0]["name"] == "NASA Earthdata Search"
        assert c2_result.exploration_links[1]["name"] == "Fetched Tool"
        assert c2_result.exploration_links[1]["url"] == "https://fetched.example.com"

    def test_raises_tool_association_error_on_cmr_failure(self, monkeypatch):
        """Should raise ToolAssociationError when CMR fetch fails for any collection."""
        collection = _make_collection("C1-P")

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            MagicMock(side_effect=RuntimeError("CMR unreachable")),
        )

        with pytest.raises(ToolAssociationError, match="C1-P"):
            enrich_with_tool_associations([collection])

    def test_error_message_includes_concept_id(self, monkeypatch):
        """ToolAssociationError should name the failing collection for diagnostics."""
        collection = _make_collection("C9999-FAILING")

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            MagicMock(side_effect=Exception("network error")),
        )

        with pytest.raises(ToolAssociationError, match="C9999-FAILING"):
            enrich_with_tool_associations([collection])

    def test_does_not_write_to_cache_on_failure(self, monkeypatch):
        """Cache should not be poisoned when CMR fetch fails."""
        collection = _make_collection("C1-P")

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            MagicMock(side_effect=Exception("oops")),
        )

        with pytest.raises(ToolAssociationError):
            enrich_with_tool_associations([collection])

        cache.set.assert_not_called()


# ---------------------------------------------------------------------------
# _round_bbox
# ---------------------------------------------------------------------------


class TestRoundBbox:
    """Tests for _round_bbox helper."""

    def test_rounds_coordinates_to_five_decimals(self):
        """Each coordinate should be rounded to 5 decimal places."""
        result = _round_bbox("-92.359312345,30.365023456,-77.909553456,45.563671234")
        assert result == "-92.35931,30.36502,-77.90955,45.56367"

    def test_preserves_exact_values(self):
        """Coordinates already within 5 decimals should be unchanged."""
        assert _round_bbox("-10.0,20.0,30.0,60.0") == "-10.0,20.0,30.0,60.0"

    def test_rounds_negative_coordinates(self):
        """Should round negative values correctly."""
        result = _round_bbox("-180.123456,-90.123456,180.123456,90.123456")
        assert result == "-180.12346,-90.12346,180.12346,90.12346"

    def test_earthdata_search_sb_param_is_rounded(self):
        """The sb[0]= value in an EDS link should be rounded to 5 decimal places."""
        spatial = SpatialConstraint(
            wkt_geometry="POLYGON((-92.35931234 30.36502345, -77.90955345 30.36502345, -77.90955345 45.56367123, -92.35931234 45.56367123, -92.35931234 30.36502345))"
        )
        link = _earthdata_search_link("C1-P", spatial=spatial)
        # Extract just the sb[0]= value and check its coordinates are ≤5 decimal places
        import re

        sb_match = re.search(r"sb\[0\]=([^&]+)", link["url"])
        assert sb_match, "sb[0]= param not found in URL"
        coords = re.findall(r"-?\d+\.\d+", sb_match.group(1))
        for coord in coords:
            assert len(coord.split(".")[1]) <= 5, f"{coord} has more than 5 decimal places"


# ---------------------------------------------------------------------------
# _map_center_zoom
# ---------------------------------------------------------------------------


class TestMapCenterZoom:
    """Tests for _map_center_zoom helper."""

    def test_returns_correct_center_lat(self):
        """Center latitude should be the midpoint of south and north."""
        lat, _lon, _zoom = _map_center_zoom("-10.0,20.0,30.0,50.0")
        assert lat == 35.0

    def test_returns_correct_center_lon(self):
        """Center longitude should be the midpoint of west and east."""
        _lat, lon, _zoom = _map_center_zoom("-10.0,20.0,30.0,50.0")
        assert lon == 10.0

    def test_zoom_is_positive(self):
        """Zoom should be a positive float for any valid bbox."""
        _lat, _lon, zoom = _map_center_zoom("-180.0,-90.0,180.0,90.0")
        assert zoom > 0

    def test_smaller_bbox_gives_higher_zoom(self):
        """A tighter bbox should produce a higher zoom level than a large one."""
        _l, _n, zoom_large = _map_center_zoom("-180.0,-90.0,180.0,90.0")
        _l, _n, zoom_small = _map_center_zoom("-5.0,45.0,5.0,55.0")
        assert zoom_small > zoom_large

    def test_point_bbox_does_not_raise(self):
        """A zero-area bbox (point) should not raise ZeroDivisionError."""
        lat, lon, zoom = _map_center_zoom("10.0,20.0,10.0,20.0")
        assert lat == 20.0
        assert lon == 10.0
        assert zoom > 0


# ---------------------------------------------------------------------------
# _bbox_from_wkt
# ---------------------------------------------------------------------------


class TestBboxFromWkt:
    """Tests for _bbox_from_wkt helper."""

    def test_extracts_bbox_from_polygon(self):
        """Should return west,south,east,north from a simple polygon."""
        wkt = "POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))"
        assert _bbox_from_wkt(wkt) == "-10.0,20.0,30.0,60.0"

    def test_extracts_bbox_from_point(self):
        """A point WKT should produce a degenerate bbox with equal min/max."""
        wkt = "POINT(-104.9 39.7)"
        assert _bbox_from_wkt(wkt) == "-104.9,39.7,-104.9,39.7"

    def test_returns_none_for_invalid_wkt(self):
        """Should return None when no coordinate pairs can be parsed."""
        assert _bbox_from_wkt("NOT_A_WKT") is None

    def test_returns_none_for_empty_string(self):
        """Should return None for an empty string."""
        assert _bbox_from_wkt("") is None

    def test_handles_negative_coordinates(self):
        """Should correctly handle negative longitudes and latitudes."""
        wkt = "POLYGON((-180 -90, 180 -90, 180 90, -180 90, -180 -90))"
        assert _bbox_from_wkt(wkt) == "-180.0,-90.0,180.0,90.0"


# ---------------------------------------------------------------------------
# _resolve_value
# ---------------------------------------------------------------------------


class TestResolveValue:
    """Tests for _resolve_value — maps ValueType URI to a concrete string."""

    def test_resolves_start_date(self):
        t = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
        result = _resolve_value("https://schema.org/startDate", "C1-P", t, None)
        assert result == datetime(2020, 1, 1, tzinfo=UTC).isoformat()

    def test_resolves_start_time(self):
        t = TemporalConstraint(start_date=datetime(2020, 6, 15, tzinfo=UTC))
        result = _resolve_value("https://schema.org/startTime", "C1-P", t, None)
        assert result == datetime(2020, 6, 15, tzinfo=UTC).isoformat()

    def test_resolves_end_date(self):
        t = TemporalConstraint(end_date=datetime(2020, 12, 31, tzinfo=UTC))
        result = _resolve_value("https://schema.org/endDate", "C1-P", t, None)
        assert result == datetime(2020, 12, 31, tzinfo=UTC).isoformat()

    def test_resolves_end_time(self):
        t = TemporalConstraint(end_date=datetime(2020, 12, 31, tzinfo=UTC))
        result = _resolve_value("https://schema.org/endTime", "C1-P", t, None)
        assert result == datetime(2020, 12, 31, tzinfo=UTC).isoformat()

    def test_resolves_dataset_time_interval_with_both_bounds(self):
        t = TemporalConstraint(
            start_date=datetime(2020, 1, 1, tzinfo=UTC),
            end_date=datetime(2020, 12, 31, tzinfo=UTC),
        )
        result = _resolve_value("https://schema.org/datasetTimeInterval", "C1-P", t, None)
        assert "/" in result
        assert "2020-01-01" in result
        assert "2020-12-31" in result

    def test_resolves_interval_with_open_end(self):
        """Open-ended interval should use '..' for the missing end bound."""
        t = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=None)
        result = _resolve_value("https://schema.org/datasetTimeInterval", "C1-P", t, None)
        assert result.endswith("/..") or result.endswith("/None")

    def test_resolves_schema_box_from_wkt(self):
        s = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))")
        result = _resolve_value("https://schema.org/box", "C1-P", None, s)
        assert result == "-10.0,20.0,30.0,60.0"

    def test_resolves_cmr_concept_id(self):
        result = _resolve_value(
            "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-concept-id",
            "C9999-PROV",
            None,
            None,
        )
        assert result == "C9999-PROV"

    def test_resolves_short_name(self):
        result = _resolve_value("shortName", "C1-P", None, None, short_name="TRMM_3B42")
        assert result == "TRMM_3B42"

    def test_returns_none_for_short_name_when_not_provided(self):
        result = _resolve_value("shortName", "C1-P", None, None)
        assert result is None

    def test_returns_none_for_unknown_value_type(self):
        result = _resolve_value("longName", "C1-P", None, None)
        assert result is None

    def test_returns_none_when_value_type_is_none(self):
        result = _resolve_value(None, "C1-P", None, None)
        assert result is None

    def test_returns_none_for_start_date_when_no_temporal_constraint(self):
        result = _resolve_value("https://schema.org/startDate", "C1-P", None, None)
        assert result is None

    def test_returns_none_for_box_when_no_wkt(self):
        result = _resolve_value("https://schema.org/box", "C1-P", None, SpatialConstraint())
        assert result is None


# ---------------------------------------------------------------------------
# _expand_url_template
# ---------------------------------------------------------------------------


class TestExpandUrlTemplate:
    """Tests for _expand_url_template — minimal RFC 6570 query-string expansion."""

    def test_expands_query_string_with_known_values(self):
        """Should produce a ?key=value query string for known vars."""
        result = _expand_url_template(
            "https://example.com{?start,end}",
            {"start": "2020-01-01", "end": "2020-12-31"},
        )
        assert result == "https://example.com?start=2020-01-01&end=2020-12-31"

    def test_omits_unknown_query_vars(self):
        """Should exclude vars not in the values dict."""
        result = _expand_url_template(
            "https://example.com{?a,b,c}",
            {"a": "1"},
        )
        assert result == "https://example.com?a=1"

    def test_returns_base_url_when_all_vars_unknown(self):
        """Should produce no '?' when nothing is resolvable."""
        result = _expand_url_template("https://example.com{?a,b}", {})
        assert result == "https://example.com"

    def test_expands_simple_path_variable(self):
        """Should substitute {var} in the path."""
        result = _expand_url_template("https://example.com/{cid}/data", {"cid": "C1-P"})
        assert result == "https://example.com/C1-P/data"

    def test_passes_through_url_without_templates(self):
        """A URL with no template expressions should be returned unchanged."""
        url = "https://static.example.com/viewer"
        assert _expand_url_template(url, {}) == url

    def test_giovanni_like_template(self):
        """Should correctly expand a template similar to the Giovanni PotentialAction."""
        template = (
            "https://giovanni.example.com/#service=TmAvMp{?dataKeyword,starttime,endtime,bbox}"
        )
        values = {
            "starttime": "2020-01-01T00:00:00+00:00",
            "endtime": "2020-12-31T00:00:00+00:00",
            "bbox": "-10.0,20.0,30.0,60.0",
        }
        result = _expand_url_template(template, values)
        assert result.startswith("https://giovanni.example.com/#service=TmAvMp?")
        assert "starttime=" in result
        assert "endtime=" in result
        assert "bbox=" in result
        assert "dataKeyword" not in result  # not in values, should be omitted

    # --- RFC 6570 reserved expansion {+var} ---

    def test_expands_reserved_var_with_known_value(self):
        """{+var} should be substituted when the value is present."""
        result = _expand_url_template(
            "https://soto.example.com/?t={+date}",
            {"date": "2020-01-15"},
        )
        assert result == "https://soto.example.com/?t=2020-01-15"

    def test_strips_empty_reserved_var_from_query(self):
        """{+var} with no value should remove the surrounding parameter entirely."""
        result = _expand_url_template(
            "https://soto.example.com/?l={+layers}&t={+date}",
            {},
        )
        # Both params have no value — query string should be gone entirely
        assert result == "https://soto.example.com/"

    def test_strips_only_missing_reserved_vars(self):
        """{+var} present values should be kept; missing ones should be dropped."""
        result = _expand_url_template(
            "https://soto.example.com/?l={+layers}&t={+date}",
            {"date": "2020-01-15"},
        )
        assert "t=2020-01-15" in result
        assert "l=" not in result

    def test_soto_url_without_temporal_strips_t_param(self):
        """The real SOTO URL template t={+date} should be removed when date is None."""
        template = "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}&t={+date}"
        result = _expand_url_template(template, {})
        assert "{+date}" not in result
        assert "{+layers}" not in result
        assert "t=" not in result
        assert "l=" not in result


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# _preferred_projection
# ---------------------------------------------------------------------------


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

    _GEO_LAYER = {
        "product": "MODIS_Terra_Geo",
        "geographic": True,
        "arctic": False,
        "antarctic": False,
    }
    _ARCTIC_LAYER = {
        "product": "MODIS_Terra_Arctic",
        "geographic": False,
        "arctic": True,
        "antarctic": False,
    }
    _ANTARCTIC_LAYER = {
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

    _GEO_LAYER_A = {"product": "LayerGeoA", "geographic": True, "arctic": False, "antarctic": False}
    _GEO_LAYER_B = {"product": "LayerGeoB", "geographic": True, "arctic": False, "antarctic": False}
    _ARCTIC_LAYER = {
        "product": "LayerArctic",
        "geographic": False,
        "arctic": True,
        "antarctic": False,
    }
    _ANTARCTIC_LAYER = {
        "product": "LayerAntarctic",
        "geographic": False,
        "arctic": False,
        "antarctic": True,
    }

    def _tags(self, layers: list) -> dict:
        return {"edsc.extra.serverless.gibs": {"data": layers}}

    def test_returns_empty_list_when_no_tags(self):
        """Should return empty list when tags is empty."""
        assert _all_gibs_layers({}, None) == []

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
        assert result == []

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
        assert result == []

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
        assert result == []

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


class TestResolveToolUrl:
    """Tests for _resolve_tool_url — maps raw tool dict + context to {name, url}."""

    def test_produces_name_and_resolved_url(self):
        """Should return a dict with name and a URL populated from context."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?starttime,endtime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
                {
                    "value_name": "endtime",
                    "value_type": "https://schema.org/endDate",
                    "required": False,
                },
            ],
        }
        temporal = TemporalConstraint(
            start_date=datetime(2020, 1, 1, tzinfo=UTC),
            end_date=datetime(2020, 12, 31, tzinfo=UTC),
        )
        result = _resolve_tool_url(tool, "C1-P", temporal, None)
        assert result["name"] == "Giovanni"
        assert "starttime=" in result["url"]
        assert "endtime=" in result["url"]

    def test_injects_single_gibs_layer_with_base_layer(self):
        """Single GIBS layer should appear followed by BlueMarble_NextGeneration."""
        tool = {
            "name": "SOTO",
            "url_template": "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}",
            "query_inputs": [],
        }
        result = _resolve_tool_url(
            tool, "C1-P", None, None, gibs_layers=["MODIS_Terra_CorrectedReflectance_TrueColor"]
        )
        assert (
            "l=MODIS_Terra_CorrectedReflectance_TrueColor,BlueMarble_NextGeneration"
            in result["url"]
        )

    def test_multiple_gibs_layers_hidden_with_base_layer(self):
        """Secondary layers should be (hidden); BlueMarble_NextGeneration appended last."""
        tool = {
            "name": "SOTO",
            "url_template": "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}",
            "query_inputs": [],
        }
        result = _resolve_tool_url(
            tool,
            "C1-P",
            None,
            None,
            gibs_layers=["LayerA", "LayerB", "LayerC"],
        )
        assert "l=LayerA,LayerB(hidden),LayerC(hidden),BlueMarble_NextGeneration" in result["url"]

    def test_strips_layers_param_when_gibs_layers_is_empty(self):
        """Should remove l= from URL when gibs_layers is empty."""
        tool = {
            "name": "SOTO",
            "url_template": "https://soto.podaac.earthdatacloud.nasa.gov/?l={+layers}&t={+date}",
            "query_inputs": [],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None, gibs_layers=[])
        assert "l=" not in result["url"]
        assert "{+layers}" not in result["url"]

    def test_returns_none_url_when_no_template(self):
        """Should fall back to base_url when url_template is absent."""
        tool = {"name": "My Tool", "url_template": None, "base_url": None, "query_inputs": []}
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result == {"name": "My Tool", "url": None, "topic": None}

    def test_falls_back_to_base_url_when_no_template(self):
        """Should return base_url as url when url_template is absent but base_url exists."""
        tool = {
            "name": "My Tool",
            "url_template": None,
            "base_url": "https://my-tool.example.com",
            "query_inputs": [],
            "topic": "Data discovery",
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result == {
            "name": "My Tool",
            "url": "https://my-tool.example.com",
            "topic": "Data discovery",
        }

    def test_omits_params_with_no_context_value(self):
        """Params whose ValueType doesn't resolve should be absent from the URL."""
        tool = {
            "name": "Tool",
            "url_template": "https://tool.example.com{?longName,starttime}",
            "query_inputs": [
                {"value_name": "longName", "value_type": "longName", "required": False},
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
            ],
        }
        temporal = TemporalConstraint(start_date=datetime(2020, 1, 1, tzinfo=UTC))
        result = _resolve_tool_url(tool, "C1-P", temporal, None)
        assert "starttime=" in result["url"]
        assert "longName" not in result["url"]

    def test_handles_empty_query_inputs(self):
        """A tool with no query_inputs should resolve to the template URL unchanged."""
        tool = {
            "name": "Static Tool",
            "url_template": "https://static.example.com/viewer",
            "query_inputs": [],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result == {
            "name": "Static Tool",
            "url": "https://static.example.com/viewer",
            "topic": None,
        }

    def test_resolves_concept_id_param(self):
        """Should fill concept_id when ValueType is the CMR concept ID URI."""
        tool = {
            "name": "Earthdata Search",
            "url_template": "https://search.earthdata.nasa.gov/search?q={cid}",
            "query_inputs": [
                {
                    "value_name": "cid",
                    "value_type": "https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html#c-concept-id",
                    "required": True,
                }
            ],
        }
        result = _resolve_tool_url(tool, "C9999-PROV", None, None)
        assert "C9999-PROV" in result["url"]

    def test_resolves_bbox_from_spatial_constraint(self):
        """Should substitute bbox when ValueType is schema.org/box."""
        tool = {
            "name": "Map Viewer",
            "url_template": "https://map.example.com{?bbox}",
            "query_inputs": [
                {"value_name": "bbox", "value_type": "https://schema.org/box", "required": False}
            ],
        }
        spatial = SpatialConstraint(wkt_geometry="POLYGON((-10 20, 30 20, 30 60, -10 60, -10 20))")
        result = _resolve_tool_url(tool, "C1-P", None, spatial)
        assert "bbox=" in result["url"]
        assert "-10.0" in result["url"]

    def test_topic_is_surfaced_in_resolved_link(self):
        """topic from the raw tool dict should appear in the resolved link."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com/",
            "query_inputs": [],
            "topic": "Data analysis and visualization",
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result["topic"] == "Data analysis and visualization"

    def test_resolves_short_name_param(self):
        """Should fill shortName when ValueType is 'shortName' and short_name is provided."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?dataKeyword}",
            "query_inputs": [
                {"value_name": "dataKeyword", "value_type": "shortName", "required": False}
            ],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None, short_name="TRMM_3B42")
        assert "dataKeyword=TRMM_3B42" in result["url"]

    def test_omits_short_name_param_when_not_available(self):
        """Should omit the shortName param when no short_name is provided."""
        tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?dataKeyword}",
            "query_inputs": [
                {"value_name": "dataKeyword", "value_type": "shortName", "required": False}
            ],
        }
        result = _resolve_tool_url(tool, "C1-P", None, None)
        assert result["url"] == "https://giovanni.example.com"

    def test_passes_temporal_and_spatial_to_resolver(self, monkeypatch):
        """URL resolution should use the temporal and spatial constraints supplied."""
        collection = _make_collection("C1-P")
        temporal = TemporalConstraint(
            start_date=datetime(2021, 3, 1, tzinfo=UTC),
            end_date=datetime(2021, 9, 30, tzinfo=UTC),
        )
        spatial = SpatialConstraint(wkt_geometry="POLYGON((10 20, 50 20, 50 60, 10 60, 10 20))")
        raw_tool = {
            "name": "Giovanni",
            "url_template": "https://giovanni.example.com{?starttime,endtime,bbox}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
                {
                    "value_name": "endtime",
                    "value_type": "https://schema.org/endDate",
                    "required": False,
                },
                {"value_name": "bbox", "value_type": "https://schema.org/box", "required": False},
            ],
        }

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: {"tools": [raw_tool], "tags": {}},
        )

        result = enrich_with_tool_associations([collection], temporal=temporal, spatial=spatial)

        # Index [0] is Earthdata Search; Giovanni is at [1]
        url = result[0].exploration_links[1]["url"]
        assert "2021-03-01" in url
        assert "2021-09-30" in url
        assert "bbox=" in url

    def test_enriches_multiple_collections_concurrently(self, monkeypatch):
        """All collections should be enriched even when fetched via thread pool."""
        collections = [_make_collection(f"C{i}-P") for i in range(5)]
        # Static URLs so resolved url == url_template
        raw_by_id = {
            f"C{i}-P": [
                {
                    "name": f"Tool {i}",
                    "url_template": f"https://t{i}.example.com",
                    "query_inputs": [],
                }
            ]
            for i in range(5)
        }

        cache = _make_cache()
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations.get_cache_client",
            lambda: cache,
        )
        monkeypatch.setattr(
            "tools.discover_data.utils.tool_associations._fetch_tool_associations",
            lambda cid: {"tools": raw_by_id[cid], "tags": {}},
        )

        result = enrich_with_tool_associations(collections)

        assert len(result) == 5
        for col in result:
            i = int(col.concept_id[1])
            # Index [0] is always Earthdata Search; CMR tool is at [1]
            assert len(col.exploration_links) == 2
            assert col.exploration_links[0]["name"] == "NASA Earthdata Search"
            assert col.exploration_links[1] == {
                "name": f"Tool {i}",
                "url": f"https://t{i}.example.com",
                "topic": None,
            }


# ---------------------------------------------------------------------------
# _earthdata_search_link
# ---------------------------------------------------------------------------


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

    def test_adds_qt_upper_bound_from_collection_end_date_when_no_temporal(self):
        """qt=,end should be set from collection_end_date when no query temporal is present."""
        end = datetime(2020, 12, 31, tzinfo=UTC)
        link = _earthdata_search_link("C1-P", temporal=None, collection_end_date=end)
        assert "qt=" in link["url"]
        assert "%2C2020-12-31" in link["url"]  # URL-encoded leading comma (,end)

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


# ---------------------------------------------------------------------------
# _worldview_link
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _build_exploration_links
# ---------------------------------------------------------------------------


class TestBuildExplorationLinks:
    """Tests for _build_exploration_links helper."""

    _STATIC_TOOL = {
        "name": "Static Tool",
        "url_template": "https://other.example.com/viewer",
        "query_inputs": [],
        "base_url": "https://other.example.com",
    }

    def test_earthdata_search_always_first(self):
        """Earthdata Search should be the first exploration link for any collection."""
        links = _build_exploration_links([], "C1-P", None, None, None, [])
        assert links[0]["name"] == "NASA Earthdata Search"

    def test_earthdata_search_present_when_no_tools_and_no_gibs(self):
        """Should still return NASA Earthdata Search even with no CMR tools and no GIBS layer."""
        links = _build_exploration_links([], "C1-P", None, None, None, [])
        assert len(links) == 1
        assert links[0]["name"] == "NASA Earthdata Search"

    def test_worldview_added_when_gibs_layer_provided(self):
        """Worldview link should appear immediately after Earthdata Search when GIBS layers are set."""
        links = _build_exploration_links([], "C1-P", None, None, None, ["MODIS_Terra_TrueColor"])
        assert len(links) == 2
        assert links[1]["name"] == "NASA Worldview"
        assert "MODIS_Terra_TrueColor" in links[1]["url"]
        assert "BlueMarble_NextGeneration" in links[1]["url"]

    def test_worldview_not_added_when_no_gibs_layer(self):
        """Worldview should be absent when gibs_layers is empty."""
        links = _build_exploration_links([], "C1-P", None, None, None, [])
        assert all(link["name"] != "NASA Worldview" for link in links)

    def test_cmr_tools_appended_after_guaranteed_links(self):
        """CMR tools should appear after Earthdata Search (and Worldview if present)."""
        links = _build_exploration_links([self._STATIC_TOOL], "C1-P", None, None, None, [])
        assert links[0]["name"] == "NASA Earthdata Search"
        assert links[1]["name"] == "Static Tool"

    def test_deduplicates_cmr_tool_with_earthdata_search_base_url(self):
        """CMR tool whose base_url is Earthdata Search should be skipped to avoid duplication."""
        eds_tool = {
            "name": "Earthdata Search Tool",
            "url_template": "https://search.earthdata.nasa.gov/search?p={cid}",
            "query_inputs": [],
            "base_url": "https://search.earthdata.nasa.gov",
        }
        links = _build_exploration_links([eds_tool], "C1-P", None, None, None, [])
        names = [link["name"] for link in links]
        assert names.count("Earthdata Search Tool") == 0
        assert "NASA Earthdata Search" in names  # our guaranteed link remains

    def test_deduplicates_cmr_tool_with_worldview_base_url(self):
        """CMR tool whose base_url is Worldview should be skipped when Worldview is already present."""
        wv_tool = {
            "name": "Worldview Tool",
            "url_template": "https://worldview.earthdata.nasa.gov/?l=Layer",
            "query_inputs": [],
            "base_url": "https://worldview.earthdata.nasa.gov",
        }
        links = _build_exploration_links([wv_tool], "C1-P", None, None, None, ["SomeLayer"])
        names = [link["name"] for link in links]
        assert names.count("Worldview Tool") == 0
        assert "NASA Worldview" in names  # our guaranteed link remains

    def test_non_dedup_cmr_tools_are_included(self):
        """Tools whose base_url is not Earthdata Search or Worldview should pass through."""
        links = _build_exploration_links([self._STATIC_TOOL], "C1-P", None, None, None, [])
        assert any(link["name"] == "Static Tool" for link in links)

    def test_multiple_gibs_layers_all_appear_in_worldview_url(self):
        """All GIBS layers should appear in the Worldview l= parameter."""
        links = _build_exploration_links([], "C1-P", None, None, None, ["LayerA", "LayerB"])
        wv = next(l for l in links if l["name"] == "NASA Worldview")
        assert "LayerA" in wv["url"]
        assert "LayerB" in wv["url"]


class TestPrioritizeTools:
    """Tests for _prioritize_tools."""

    def _make_tool(
        self,
        name: str,
        topic: str | None = None,
        url_template: str | None = None,
    ) -> dict:
        return {
            "name": name,
            "topic": topic,
            "url_template": url_template,
            "base_url": "https://example.com",
            "query_inputs": [],
        }

    def test_visualization_tools_sorted_first(self):
        """Tools whose topic contains 'visualization' should appear before others."""
        tools = [
            self._make_tool("Plain Tool", topic="Data access"),
            self._make_tool("Viz Tool", topic="Data analysis and visualization"),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Viz Tool"
        assert result[1]["name"] == "Plain Tool"

    def test_tools_with_url_template_sorted_before_base_url_only(self):
        """Within the same topic tier, tools with a URL template rank higher."""
        tools = [
            self._make_tool("Base-URL Only", topic="Data access"),
            self._make_tool(
                "Deep Link", topic="Data access", url_template="https://example.com{?q}"
            ),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Deep Link"
        assert result[1]["name"] == "Base-URL Only"

    def test_visualization_with_template_beats_visualization_without(self):
        """Visualization + URL template beats visualization with base_url only."""
        tools = [
            self._make_tool("Viz No Template", topic="Earth science visualization"),
            self._make_tool(
                "Viz With Template",
                topic="Earth science visualization",
                url_template="https://t.example.com{?q}",
            ),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Viz With Template"
        assert result[1]["name"] == "Viz No Template"

    def test_returns_all_tools_regardless_of_count(self):
        """Should return all tools without truncating."""
        tools = [self._make_tool(f"Tool {i}") for i in range(6)]

        result = _prioritize_tools(tools)

        assert len(result) == 6

    def test_returns_all_when_three_or_fewer(self):
        """Should not truncate if the input has 3 or fewer tools."""
        tools = [self._make_tool(f"Tool {i}") for i in range(2)]

        result = _prioritize_tools(tools)

        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        """Should return an empty list without raising."""
        assert _prioritize_tools([]) == []

    def test_visualization_beats_non_visualization_regardless_of_template(self):
        """Visualization tools should rank above non-visualization deep links."""
        tools = [
            self._make_tool(
                "Non-Viz Deep Link", topic="Data access", url_template="https://a.com{?q}"
            ),
            self._make_tool("Viz Base Only", topic="Earth science visualization"),
        ]

        result = _prioritize_tools(tools)

        assert result[0]["name"] == "Viz Base Only"
        assert result[1]["name"] == "Non-Viz Deep Link"
