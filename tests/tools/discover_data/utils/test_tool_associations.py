"""Tests for tool association enrichment."""

# pylint: disable=too-many-lines
import hashlib
from datetime import UTC, datetime
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from models.tools.discover_data import CollectionMatch, TemporalConstraint
from tools.discover_data.utils.tool_associations import (
    TOOL_ASSOC_CACHE_TTL,
    ToolAssociationError,
    _build_exploration_links,
    _cache_key,
    _fetch_tool_associations,
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
    cache.get.side_effect = (hits or {}).get
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
        tools = [{"name": "Tool A", "url_template": "https://tool.example.com", "query_inputs": []}]
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
            lambda ids: fetch_metadata_calls.append(ids) or tools,
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

    def test_returns_empty_tools_when_tool_ids_exist_but_tool_metadata_is_empty(self, monkeypatch):
        """Empty actionable metadata for reported tool IDs should be non-fatal."""
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
            lambda ids: [],
        )

        result = _fetch_tool_associations("C1234-PROVIDER")

        assert result["tools"] == []
        assert result["tags"] == {}

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

        assert not result
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
# TestBuildExplorationLinks
# ---------------------------------------------------------------------------


class TestBuildExplorationLinks:
    """Tests for _build_exploration_links helper."""

    _STATIC_TOOL: ClassVar[dict] = {
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

    def test_deduplicates_earthdata_tool_with_http_base_url(self):
        """Earthdata-based tools should be deduped even when metadata uses http."""
        eds_tool = {
            "name": "Earthdata Search Tool",
            "url_template": "http://search.earthdata.nasa.gov/search?p={cid}",
            "query_inputs": [],
            "base_url": "http://search.earthdata.nasa.gov",
        }
        links = _build_exploration_links([eds_tool], "C1-P", None, None, None, [])
        names = [link["name"] for link in links]
        assert names.count("Earthdata Search Tool") == 0

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

    def test_deduplicates_worldview_tool_with_http_base_url(self):
        """Worldview-based tools should be deduped even when metadata uses http."""
        wv_tool = {
            "name": "Worldview Tool",
            "url_template": "http://worldview.earthdata.nasa.gov/?l=Layer",
            "query_inputs": [],
            "base_url": "http://worldview.earthdata.nasa.gov",
        }
        links = _build_exploration_links([wv_tool], "C1-P", None, None, None, ["SomeLayer"])
        names = [link["name"] for link in links]
        assert names.count("Worldview Tool") == 0

    def test_keeps_worldview_cmr_tool_when_no_worldview_link_added(self):
        """Worldview-base CMR tool should not be deduped when gibs_layers is empty."""
        wv_tool = {
            "name": "Worldview Tool",
            "url_template": "https://worldview.earthdata.nasa.gov/?l=Layer",
            "query_inputs": [],
            "base_url": "https://worldview.earthdata.nasa.gov",
        }
        links = _build_exploration_links([wv_tool], "C1-P", None, None, None, [])
        names = [link["name"] for link in links]
        assert "NASA Worldview" not in names
        assert "Worldview Tool" in names

    def test_keeps_http_worldview_cmr_tool_when_no_worldview_link_added(self):
        """Worldview http metadata should still be kept when no guaranteed Worldview link exists."""
        wv_tool = {
            "name": "Worldview Tool",
            "url_template": "http://worldview.earthdata.nasa.gov/?l=Layer",
            "query_inputs": [],
            "base_url": "http://worldview.earthdata.nasa.gov",
        }
        links = _build_exploration_links([wv_tool], "C1-P", None, None, None, [])
        names = [link["name"] for link in links]
        assert "Worldview Tool" in names

    def test_non_dedup_cmr_tools_are_included(self):
        """Tools whose base_url is not Earthdata Search or Worldview should pass through."""
        links = _build_exploration_links([self._STATIC_TOOL], "C1-P", None, None, None, [])
        assert any(link["name"] == "Static Tool" for link in links)

    def test_skips_tool_when_required_input_missing(self):
        """Tools missing required template inputs should be omitted from exploration links."""
        required_tool = {
            "name": "Required Tool",
            "base_url": "https://tool.example.com/home",
            "url_template": "https://tool.example.com{?starttime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                }
            ],
        }

        links = _build_exploration_links([required_tool], "C1-P", None, None, None, [])
        names = [link["name"] for link in links]
        assert "Required Tool" not in names

    def test_multiple_gibs_layers_all_appear_in_worldview_url(self):
        """All GIBS layers should appear in the Worldview l= parameter."""
        links = _build_exploration_links([], "C1-P", None, None, None, ["LayerA", "LayerB"])
        wv = next(link for link in links if link["name"] == "NASA Worldview")
        assert "LayerA" in wv["url"]
        assert "LayerB" in wv["url"]

    def test_uses_collection_temporal_as_fallback_for_required_inputs(self):
        """Collection start/end should satisfy required temporal inputs when user provides none."""
        giovanni_tool = {
            "name": "Giovanni",
            "base_url": "https://giovanni.gsfc.nasa.gov/giovanni",
            "url_template": "https://giovanni.gsfc.nasa.gov/giovanni/#service=TmAvMp{?starttime,endtime}",
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
        collection_start = datetime(2000, 1, 1, tzinfo=UTC)
        collection_end = datetime(2024, 12, 31, tzinfo=UTC)

        links = _build_exploration_links(
            [giovanni_tool],
            "C1-P",
            temporal=None,
            spatial=None,
            short_name=None,
            gibs_layers=[],
            collection_start_date=collection_start,
            collection_end_date=collection_end,
        )
        names = [link["name"] for link in links]
        assert "Giovanni" in names
        giovanni_link = next(link for link in links if link["name"] == "Giovanni")
        assert "starttime=2000-01-01" in giovanni_link["url"]
        assert "endtime=2024-12-31" in giovanni_link["url"]

    def test_user_temporal_takes_precedence_over_collection_fallback(self):
        """Explicit user temporal should override collection start/end in tool URL resolution."""
        tool = {
            "name": "Giovanni",
            "base_url": "https://giovanni.gsfc.nasa.gov/giovanni",
            "url_template": "https://giovanni.gsfc.nasa.gov/giovanni/#service=TmAvMp{?starttime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
            ],
        }
        user_temporal = TemporalConstraint(start_date=datetime(2020, 6, 1, tzinfo=UTC))

        links = _build_exploration_links(
            [tool],
            "C1-P",
            temporal=user_temporal,
            spatial=None,
            short_name=None,
            gibs_layers=[],
            collection_start_date=datetime(2000, 1, 1, tzinfo=UTC),
            collection_end_date=datetime(2024, 12, 31, tzinfo=UTC),
        )
        giovanni_link = next(link for link in links if link["name"] == "Giovanni")
        assert "starttime=2020-06-01" in giovanni_link["url"]
        assert "2000-01-01" not in giovanni_link["url"]

    def test_empty_user_temporal_still_uses_collection_fallback(self):
        """TemporalConstraint with no bounds should be treated as absent for fallback behavior."""
        tool = {
            "name": "Giovanni",
            "base_url": "https://giovanni.gsfc.nasa.gov/giovanni",
            "url_template": "https://giovanni.gsfc.nasa.gov/giovanni/#service=TmAvMp{?starttime}",
            "query_inputs": [
                {
                    "value_name": "starttime",
                    "value_type": "https://schema.org/startDate",
                    "required": True,
                },
            ],
        }

        links = _build_exploration_links(
            [tool],
            "C1-P",
            temporal=TemporalConstraint(),
            spatial=None,
            short_name=None,
            gibs_layers=[],
            collection_start_date=datetime(2000, 1, 1, tzinfo=UTC),
            collection_end_date=datetime(2024, 12, 31, tzinfo=UTC),
        )

        giovanni_link = next(link for link in links if link["name"] == "Giovanni")
        assert "starttime=2000-01-01" in giovanni_link["url"]
