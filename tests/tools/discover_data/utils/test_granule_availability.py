"""Tests for granule availability validation."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from tools.discover_data.utils import granule_availability
from tools.discover_data.utils.granule_availability import GranuleValidationError
from tools.models.output_model import CollectionMatch
from util.cmr.client import CMRError, CMRSearchResponse


class TestCountGranules:
    """Tests for _count_granules function."""

    def test_count_granules_no_constraints(self, monkeypatch):
        """Test counting granules without temporal/spatial constraints."""
        mock_response = CMRSearchResponse(
            items=[],
            total_hits=150,
            took_ms=25,
            search_after=None,
            page_size=0,
        )
        mock_search = Mock(return_value=iter([mock_response]))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        hits, took = granule_availability._count_granules("C1234-PROVIDER")

        assert hits == 150
        assert took == 25
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args[1]["concept_type"] == "granule"
        assert call_args[1]["search_params"]["collection_concept_id"] == "C1234-PROVIDER"
        assert not call_args[1]["page_size"]
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["files"] is None

    def test_count_granules_with_temporal_constraint(self, monkeypatch):
        """Test counting granules with temporal constraints."""
        mock_response = CMRSearchResponse(
            items=[],
            total_hits=50,
            took_ms=30,
            search_after=None,
            page_size=0,
        )
        start = datetime(2023, 1, 1, tzinfo=UTC)
        end = datetime(2023, 12, 31, tzinfo=UTC)

        mock_search = Mock(return_value=iter([mock_response]))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        hits, took = granule_availability._count_granules(
            "C1234-PROVIDER",
            temporal_start=start,
            temporal_end=end,
        )

        assert hits == 50
        assert took == 30
        call_args = mock_search.call_args
        params = call_args[1]["search_params"]
        assert "temporal" in params
        # Should format with Z suffix (not +00:00)
        assert params["temporal"] == "2023-01-01T00:00:00Z,2023-12-31T00:00:00Z"

    def test_count_granules_with_start_only_temporal(self, monkeypatch):
        """Test that only temporal_start produces an open-ended end range."""
        mock_response = CMRSearchResponse(
            items=[],
            total_hits=80,
            took_ms=20,
            search_after=None,
            page_size=0,
        )
        start = datetime(2020, 6, 1, tzinfo=UTC)

        mock_search = Mock(return_value=iter([mock_response]))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        hits, _ = granule_availability._count_granules(
            "C1234-PROVIDER",
            temporal_start=start,
        )

        assert hits == 80
        call_args = mock_search.call_args
        params = call_args[1]["search_params"]
        assert "temporal" in params
        # Start-only: comma present with empty end
        assert params["temporal"] == "2020-06-01T00:00:00Z,"

    def test_count_granules_with_end_only_temporal(self, monkeypatch):
        """Test that only temporal_end produces an open-ended start range."""
        mock_response = CMRSearchResponse(
            items=[],
            total_hits=60,
            took_ms=15,
            search_after=None,
            page_size=0,
        )
        end = datetime(2021, 3, 31, tzinfo=UTC)

        mock_search = Mock(return_value=iter([mock_response]))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        hits, _ = granule_availability._count_granules(
            "C1234-PROVIDER",
            temporal_end=end,
        )

        assert hits == 60
        call_args = mock_search.call_args
        params = call_args[1]["search_params"]
        assert "temporal" in params
        # End-only: comma present with empty start
        assert params["temporal"] == ",2021-03-31T00:00:00Z"

    def test_count_granules_with_spatial_constraint(self, monkeypatch):
        """Test counting granules with spatial constraints."""
        mock_response = CMRSearchResponse(
            items=[],
            total_hits=25,
            took_ms=45,
            search_after=None,
            page_size=0,
        )
        wkt = "POLYGON((-180 -90,-180 90,180 90,180 -90,-180 -90))"

        mock_search = Mock(return_value=iter([mock_response]))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        hits, took = granule_availability._count_granules(
            "C1234-PROVIDER",
            spatial_wkt=wkt,
        )

        assert hits == 25
        assert took == 45
        call_args = mock_search.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["files"] is not None

    def test_count_granules_cmr_error(self, monkeypatch):
        """Test that CMR errors are propagated."""
        mock_search = Mock(side_effect=CMRError("CMR request failed"))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        with pytest.raises(CMRError, match="CMR request failed"):
            granule_availability._count_granules("C1234-PROVIDER")

    def test_count_granules_no_response(self, monkeypatch):
        """Test handling of empty response from CMR."""
        mock_search = Mock(return_value=iter([]))
        monkeypatch.setattr(granule_availability, "search_cmr", mock_search)

        hits, took = granule_availability._count_granules("C1234-PROVIDER")

        assert not hits
        assert not took


class TestBuildCacheKey:
    """Tests for _build_cache_key function."""

    def test_cache_key_with_all_constraints(self):
        """Test cache key generation with all constraints."""
        start = datetime(2023, 1, 1, tzinfo=UTC)
        end = datetime(2023, 12, 31, tzinfo=UTC)
        wkt = "POLYGON((0 0,1 0,1 1,0 1,0 0))"

        key = granule_availability._build_cache_key("C1234-PROVIDER", start, end, wkt)

        assert key.startswith("granule_count:C1234-PROVIDER:")
        assert len(key.split(":")) == 3  # prefix:concept_id:hash

    def test_cache_key_without_constraints(self):
        """Test cache key generation without constraints."""
        key = granule_availability._build_cache_key("C1234-PROVIDER", None, None, None)

        assert key.startswith("granule_count:C1234-PROVIDER:")

    def test_cache_key_deterministic(self):
        """Test that same inputs produce same cache key."""
        start = datetime(2023, 1, 1, tzinfo=UTC)
        end = datetime(2023, 12, 31, tzinfo=UTC)
        wkt = "POLYGON((0 0,1 0,1 1,0 1,0 0))"

        key1 = granule_availability._build_cache_key("C1234-PROVIDER", start, end, wkt)
        key2 = granule_availability._build_cache_key("C1234-PROVIDER", start, end, wkt)

        assert key1 == key2

    def test_cache_key_different_for_different_constraints(self):
        """Test that different constraints produce different cache keys."""
        start1 = datetime(2023, 1, 1, tzinfo=UTC)
        start2 = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2023, 12, 31, tzinfo=UTC)

        key1 = granule_availability._build_cache_key("C1234-PROVIDER", start1, end, None)
        key2 = granule_availability._build_cache_key("C1234-PROVIDER", start2, end, None)

        assert key1 != key2


class TestGetCacheTTL:
    """Tests for _get_cache_ttl function."""

    def test_ongoing_collection_ttl(self):
        """Test that ongoing collections get short TTL."""
        ttl = granule_availability._get_cache_ttl(is_ongoing=True)
        assert ttl == 900  # 15 minutes

    def test_completed_collection_ttl(self):
        """Test that completed collections get long TTL."""
        ttl = granule_availability._get_cache_ttl(is_ongoing=False)
        assert ttl == 86400  # 24 hours


class TestValidateGranuleAvailability:
    """Tests for validate_granule_availability function."""

    def test_skips_validation_without_constraints(self, monkeypatch):
        """Test that validation is skipped when no spatial or temporal constraints exist."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Test collection",
                similarity_score=0.9,
                match_type="direct",
            )
        ]

        mock_count = Mock()
        monkeypatch.setattr(granule_availability, "_count_granules", mock_count)

        result = granule_availability.validate_granule_availability(collections, None, None, None)

        assert len(result) == 1
        assert result[0].concept_id == "C1234-PROVIDER"
        mock_count.assert_not_called()

    def test_skips_validation_only_when_no_temporal_and_no_spatial(self, monkeypatch):
        """Test that validation is only skipped when BOTH temporal bounds AND spatial are absent."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Test collection",
                similarity_score=0.9,
                match_type="direct",
            )
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        mock_count = Mock(return_value=(10, 5))
        monkeypatch.setattr(granule_availability, "_count_granules", mock_count)

        # Only temporal_end provided (no temporal_start, no spatial)
        result = granule_availability.validate_granule_availability(
            collections, None, datetime(2023, 12, 31, tzinfo=UTC), None
        )

        mock_count.assert_called_once()
        assert result[0].granule_count == 10

    def test_filters_collections_with_zero_granules(self, monkeypatch):
        """Test that collections with zero granules are filtered out."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Collection with granules",
                similarity_score=0.9,
                match_type="direct",
            ),
            CollectionMatch(
                concept_id="C5678-PROVIDER",
                title="Collection without granules",
                similarity_score=0.8,
                match_type="direct",
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        def _count_zero(collection_concept_id, *_):
            return {"C1234-PROVIDER": (100, 10), "C5678-PROVIDER": (0, 5)}[collection_concept_id]

        monkeypatch.setattr(granule_availability, "_count_granules", _count_zero)

        result = granule_availability.validate_granule_availability(
            collections, datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC), None
        )

        assert len(result) == 1
        assert result[0].concept_id == "C1234-PROVIDER"
        assert result[0].granule_count == 100

    def test_uses_cache_when_available(self, monkeypatch):
        """Test that cached results are used when available."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Cached collection",
                similarity_score=0.9,
                match_type="direct",
            )
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = {"count": 50, "timestamp": 1234567890}
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        result = granule_availability.validate_granule_availability(
            collections, datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC), None
        )

        assert len(result) == 1
        assert result[0].granule_count == 50
        mock_cache.get.assert_called_once()

    def test_cached_zero_granule_collection_excluded(self, monkeypatch):
        """Test that a cached granule count of 0 still excludes the collection."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Zero granules (cached)",
                similarity_score=0.9,
                match_type="direct",
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = {"count": 0, "timestamp": 1234567890}
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        result = granule_availability.validate_granule_availability(
            collections, datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC), None
        )

        assert len(result) == 0

    def test_caches_results_with_correct_ttl(self, monkeypatch):
        """Test that results are cached with appropriate TTL based on is_ongoing."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Ongoing collection",
                similarity_score=0.9,
                match_type="direct",
                is_ongoing=True,
            ),
            CollectionMatch(
                concept_id="C5678-PROVIDER",
                title="Completed collection",
                similarity_score=0.8,
                match_type="direct",
                is_ongoing=False,
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        mock_count = Mock(return_value=(100, 10))
        monkeypatch.setattr(granule_availability, "_count_granules", mock_count)

        granule_availability.validate_granule_availability(
            collections, datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC), None
        )

        # Use a set — thread completion order via as_completed is non-deterministic
        set_calls = mock_cache.set.call_args_list
        assert len(set_calls) == 2
        actual_ttls = {call[1]["ttl"] for call in set_calls}
        # 900s for ongoing, 86400s for completed
        assert actual_ttls == {900, 86400}

    def test_any_failure_raises_granule_validation_error(self, monkeypatch):
        """Test that any CMR failure raises GranuleValidationError instead of returning partial results."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Good collection",
                similarity_score=0.9,
                match_type="direct",
            ),
            CollectionMatch(
                concept_id="C5678-PROVIDER",
                title="Error collection",
                similarity_score=0.8,
                match_type="direct",
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        def _count_fail(collection_concept_id, *_):
            if collection_concept_id == "C5678-PROVIDER":
                raise CMRError("Failed")
            return (100, 10)

        monkeypatch.setattr(granule_availability, "_count_granules", _count_fail)

        with pytest.raises(GranuleValidationError):
            granule_availability.validate_granule_availability(
                collections,
                datetime(2023, 1, 1, tzinfo=UTC),
                datetime(2023, 12, 31, tzinfo=UTC),
                None,
            )

    def test_partial_failures_raise_granule_validation_error(self, monkeypatch):
        """Test that a CMR failure for one collection raises GranuleValidationError
        even when the other collections succeed."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Good collection",
                similarity_score=0.9,
                match_type="direct",
            ),
            CollectionMatch(
                concept_id="C5678-PROVIDER",
                title="Also good collection",
                similarity_score=0.8,
                match_type="direct",
            ),
            CollectionMatch(
                concept_id="C9999-PROVIDER",
                title="Error collection",
                similarity_score=0.7,
                match_type="direct",
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        def _count_two_pass(collection_concept_id, *_):
            if collection_concept_id == "C9999-PROVIDER":
                raise CMRError("Failed")
            return {"C1234-PROVIDER": (100, 10), "C5678-PROVIDER": (50, 5)}[collection_concept_id]

        monkeypatch.setattr(granule_availability, "_count_granules", _count_two_pass)

        with pytest.raises(GranuleValidationError):
            granule_availability.validate_granule_availability(
                collections,
                datetime(2023, 1, 1, tzinfo=UTC),
                datetime(2023, 12, 31, tzinfo=UTC),
                None,
            )

    def test_single_failure_raises_granule_validation_error(self, monkeypatch):
        """Test that even a single CMR failure raises GranuleValidationError."""
        collections = [
            CollectionMatch(
                concept_id="C1234-PROVIDER",
                title="Failing collection",
                similarity_score=0.9,
                match_type="direct",
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        mock_count = Mock(side_effect=CMRError("Network error"))
        monkeypatch.setattr(granule_availability, "_count_granules", mock_count)

        with pytest.raises(GranuleValidationError):
            granule_availability.validate_granule_availability(
                collections,
                datetime(2023, 1, 1, tzinfo=UTC),
                datetime(2023, 12, 31, tzinfo=UTC),
                None,
            )

    def test_zero_granule_collections_excluded(self, monkeypatch):
        """Test that collections with exactly 0 granules are excluded from results."""
        collections = [
            CollectionMatch(
                concept_id="C1111-PROVIDER",
                title="Has granules",
                similarity_score=0.9,
                match_type="direct",
            ),
            CollectionMatch(
                concept_id="C2222-PROVIDER",
                title="Zero granules",
                similarity_score=0.8,
                match_type="direct",
            ),
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        mock_count = Mock(
            side_effect=lambda cid, *_: {"C1111-PROVIDER": (42, 5), "C2222-PROVIDER": (0, 5)}[cid]
        )
        monkeypatch.setattr(granule_availability, "_count_granules", mock_count)

        result = granule_availability.validate_granule_availability(
            collections, datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC), None
        )

        result_ids = {c.concept_id for c in result}
        assert "C1111-PROVIDER" in result_ids  # has granules: kept
        assert "C2222-PROVIDER" not in result_ids  # zero granules: dropped

    def test_parallel_validation(self, monkeypatch):
        """Test that multiple collections are validated in parallel."""
        collections = [
            CollectionMatch(
                concept_id=f"C{i}-PROVIDER",
                title=f"Collection {i}",
                similarity_score=0.9,
                match_type="direct",
            )
            for i in range(10)
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        monkeypatch.setattr(granule_availability, "get_cache_client", lambda: mock_cache)

        mock_count = Mock(return_value=(100, 10))
        monkeypatch.setattr(granule_availability, "_count_granules", mock_count)

        result = granule_availability.validate_granule_availability(
            collections, datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC), None
        )

        assert len(result) == 10
        assert mock_count.call_count == 10
