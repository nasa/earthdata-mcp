"""Test for collection embedding tool"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import redis

from tools.collections_embeddings import tool as mod
from tools.collections_embeddings.output_model import CollectionsEmbeddingsOutput


@pytest.fixture
def mock_embedding():
    """Fixture for mock embedding vector."""
    return [0.1, 0.2, 0.3]


@pytest.fixture
def mock_query_input():
    """Minimal valid CollectionsEmbeddingsInput mock"""
    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "POLYGON ((-109 37, -109 36, -102 36, -102 37, -109 37))"
    spatial.geoLocation = "Utah"

    temporal = MagicMock()
    temporal.StartDate = datetime(2020, 1, 1)
    temporal.EndDate = datetime(2020, 12, 31)

    query = MagicMock()
    query.query = "MODIS snow cover"
    query.page_num = 1
    query.page_size = 5
    query.spatial = spatial
    query.temporal = temporal

    return query


@pytest.fixture
def mock_db_results():
    """Fixture for mock database results."""
    # (concept_id, start_date, end_date, similarity_score)
    return [
        ("C123-TEST", datetime(2020, 1, 1), datetime(2020, 12, 31), 0.91),
        ("C456-TEST", datetime(2019, 6, 1), None, 0.87),
    ]


@pytest.fixture
def mock_cmr_response():
    """Fixture for mock CMR API response."""
    return {
        "success": True,
        "data": {
            "hits": 2,
            "took": 762,
            "items": [
                {
                    "meta": {
                        "concept-id": "C123-TEST",
                        "granule-count": 100,
                    },
                    "umm": {
                        "EntryTitle": "Dataset 1",
                        "Abstract": "Abstract 1",
                    },
                },
                {
                    "meta": {
                        "concept-id": "C456-TEST",
                        "granule-count": 50,
                    },
                    "umm": {
                        "EntryTitle": "Dataset 2",
                        "Abstract": "Abstract 2",
                    },
                },
            ],
        },
    }


def test_get_cache_key_is_deterministic():
    """Test that cache key generation is deterministic."""
    key1 = mod.get_cache_key("New York")
    key2 = mod.get_cache_key(" new york ")
    assert key1 == key2
    assert key1.startswith("geocode:")


@patch.object(mod, "cache")
def test_get_from_cache_hit(mock_cache):
    """Test cache hit returns cached geometry."""
    mock_cache.get.return_value = {"geometry": "POLYGON ((1 1, 2 2, 3 3))"}

    result = mod.get_from_cache("Paris")

    assert result["geometry"].startswith("POLYGON")
    mock_cache.get.assert_called_once()


@patch.object(mod, "cache")
def test_get_from_cache_miss(mock_cache):
    """Test cache miss returns None."""
    mock_cache.get.return_value = None
    result = mod.get_from_cache("Atlantis")
    assert result is None


@patch.object(mod, "convert_text_to_geom")
def test_process_spatial_query_valid_geometry(mock_convert):
    """Test processing spatial query with valid geometry."""
    mock_convert.return_value = "POLYGON ((1 1, 2 2, 3 3))"

    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "POLYGON ((1 1, 2 2, 3 3))"
    spatial.geoLocation = None

    result = mod.process_spatial_query(spatial)

    assert "geometry" in result
    mock_convert.assert_called_once()


@patch.object(mod, "convert_text_to_geom")
@patch.object(mod, "get_from_cache")
@patch.object(mod, "langfuse")
def test_process_spatial_query_invalid_geometry_uses_cache(
    mock_langfuse, mock_cache, mock_convert
):
    """Test processing spatial query with invalid geometry uses cache."""
    mock_cache.return_value = {"geometry": "POLYGON ((cached))"}
    mock_convert.return_value = "POLYGON ((cached))"

    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "junk"
    spatial.geoLocation = "Chicago"

    result = mod.process_spatial_query(spatial)

    assert result["geometry"] == "POLYGON ((cached))"
    mock_convert.assert_called_once_with("POLYGON ((cached))")
    mock_langfuse.update_current_trace.assert_called_with(
        tags=["cache_hit", "success"],
        metadata={
            "cache_hit": True,
            "location": "Chicago",
            "location_length": 7,
        },
    )


@patch.object(mod, "fetch_cmr_data")
@patch.object(mod, "reorder_results")
@patch.object(mod, "wkt_to_cmr_params")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_cmr_collections_embeddings_happy_path(
    mock_db,
    mock_embedding_gen,
    mock_wkt,
    mock_reorder,
    mock_fetch,
    mock_query_input,
    mock_db_results,
    mock_cmr_response,
):  # pylint: disable=too-many-arguments
    """Test successful search with all components working."""
    # DB
    mock_db.connect.return_value = None
    mock_db.search.return_value = mock_db_results

    # Embedding
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2, 0.3]

    # Geometry
    mock_wkt.return_value = {"polygon[]": "dummy"}

    # CMR
    mock_fetch.return_value = mock_cmr_response
    mock_reorder.return_value = mock_cmr_response["data"]["items"]

    result = mod.search_cmr_collections_embeddings(mock_query_input)

    assert result["count"] == 2
    assert result["results"][0]["concept_id"] == "C123-TEST"
    assert "title" in result["results"][0]
    assert "abstract" in result["results"][0]

    mock_db.search.assert_called_once()
    mock_fetch.assert_called_once()


@patch.object(mod, "fetch_cmr_data")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_returns_empty_on_no_db_results(
    mock_db,
    mock_embedding_gen,
    mock_fetch,
    mock_query_input,
):
    """Test search returns empty results when database returns no results."""
    mock_db.connect.return_value = None
    mock_db.search.return_value = []
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2]

    result = mod.search_cmr_collections_embeddings(mock_query_input)

    assert result["count"] == 0
    assert result["results"] == []
    mock_fetch.assert_not_called()


@patch.object(mod, "cache")
def test_get_from_cache_redis_error(mock_cache):
    """Test redis error handling in get_from_cache"""
    mock_cache.get.side_effect = redis.RedisError("Connection failed")

    result = mod.get_from_cache("Paris")

    assert result is None
    mock_cache.get.assert_called_once()


def test_process_spatial_query_no_spatial_query():
    """Test process_spatial_query with no spatial query"""
    result = mod.process_spatial_query(None)
    assert not result


def test_process_spatial_query_no_success():
    """Test process_spatial_query with failed spatial query"""
    spatial = MagicMock()
    spatial.success = False
    spatial.geometry = "POLYGON ((1 1, 2 2, 3 3))"

    result = mod.process_spatial_query(spatial)
    assert not result


def test_process_spatial_query_no_geometry():
    """Test process_spatial_query with no geometry"""
    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = None

    result = mod.process_spatial_query(spatial)
    assert not result


@patch.object(mod, "get_from_cache")
@patch.object(mod, "langfuse")
def test_process_spatial_query_invalid_geometry_no_geolocation(_, mock_cache):
    """Test process_spatial_query with invalid geometry and no geoLocation"""
    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "junk"
    spatial.geoLocation = None

    result = mod.process_spatial_query(spatial)
    assert not result
    mock_cache.assert_not_called()


@patch.object(mod, "get_from_cache")
@patch.object(mod, "langfuse")
def test_process_spatial_query_cache_miss(mock_langfuse, mock_cache):
    """Test process_spatial_query with cache miss"""
    mock_cache.return_value = None

    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "bad"
    spatial.geoLocation = "Chicago"

    result = mod.process_spatial_query(spatial)

    assert not result
    mock_langfuse.update_current_trace.assert_called_with(
        tags=["cache_miss", "geometry_retrieval_failed"],
        metadata={
            "cache_hit": False,
            "location": "Chicago",
        },
    )


@patch.object(mod, "get_from_cache")
@patch.object(mod, "langfuse")
def test_process_spatial_query_cache_miss_no_geometry(mock_langfuse, mock_cache):
    """Test process_spatial_query with cache hit but no geometry in result"""
    mock_cache.return_value = {"some_key": "some_value"}

    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "bad"
    spatial.geoLocation = "Chicago"

    result = mod.process_spatial_query(spatial)

    assert not result
    mock_langfuse.update_current_trace.assert_called_with(
        tags=["cache_miss", "geometry_retrieval_failed"],
        metadata={
            "cache_hit": False,
            "location": "Chicago",
        },
    )


@patch.object(mod, "fetch_cmr_data")
@patch.object(mod, "langfuse")
def test_fetch_cmr_collections_metadata_cmr_error(mock_langfuse, mock_fetch):
    """Test fetch_cmr_collections_metadata with CMR error"""
    mock_fetch.return_value = {
        "success": False,
        "error": "Server error",
        "status_code": 500,
    }

    result = mod.fetch_cmr_collections_metadata(
        concept_ids=["C123-TEST"],
        similarity_scores=[0.9],
        query_params={},
        page_size=10,
    )

    assert result.count == 0
    assert result.results == []
    mock_langfuse.update_current_trace.assert_called_with(
        tags=["cmr_error"],
        metadata={
            "error": "Server error",
            "status_code": 500,
        },
    )


@patch.object(mod, "fetch_cmr_data")
@patch.object(mod, "reorder_results")
@patch.object(mod, "wkt_to_cmr_params")
@patch.object(mod, "parse_format")
def test_fetch_cmr_collections_metadata_with_geometry(
    mock_parse, mock_wkt, mock_reorder, mock_fetch
):
    """Test fetch_cmr_collections_metadata with geometry"""
    mock_parse.return_value = "umm_json"
    mock_wkt.return_value = {"polygon[]": "dummy"}
    mock_fetch.return_value = {"success": True, "data": {"items": []}}
    mock_reorder.return_value = []

    result = mod.fetch_cmr_collections_metadata(
        concept_ids=["C123-TEST"],
        similarity_scores=[0.9],
        query_params={"geometry": "POLYGON((0 0, 1 1, 2 2, 0 0))"},
        page_size=10,
    )

    mock_wkt.assert_called_once_with("POLYGON((0 0, 1 1, 2 2, 0 0))")
    assert result.count == 0


@patch.object(mod, "fetch_cmr_data")
@patch.object(mod, "reorder_results")
@patch.object(mod, "parse_format")
def test_fetch_cmr_collections_metadata_with_temporal(
    mock_parse, mock_reorder, mock_fetch
):
    """Test fetch_cmr_collections_metadata with temporal parameters"""
    mock_parse.return_value = "umm_json"
    mock_fetch.return_value = {"success": True, "data": {"items": []}}
    mock_reorder.return_value = []

    result = mod.fetch_cmr_collections_metadata(
        concept_ids=["C123-TEST"],
        similarity_scores=[0.9],
        query_params={
            "start_date": "2020-01-01T00:00:00+00:00",
            "end_date": "2020-12-31T23:59:59+00:00",
        },
        page_size=10,
    )

    # Check that fetch_cmr_data was called with temporal parameters
    call_args = mock_fetch.call_args
    params = call_args[1]["params"]
    assert "temporal[]" in params
    assert params["temporal[]"] == "2020-01-01T00:00:00Z,2020-12-31T23:59:59Z"
    assert result.count == 0


@patch.object(mod, "fetch_cmr_data")
@patch.object(mod, "reorder_results")
@patch.object(mod, "parse_format")
@patch.object(mod, "langfuse")
def test_fetch_cmr_collections_metadata_json_format(
    mock_langfuse, mock_parse, mock_reorder, mock_fetch
):
    """Test fetch_cmr_collections_metadata with json format"""
    mock_parse.return_value = "json"
    mock_fetch.return_value = {"success": True, "data": {"items": []}}
    mock_reorder.return_value = [
        {
            "id": "C123-TEST",
            "title": "Test Dataset",
            "summary": "Test Abstract",
        }
    ]

    result = mod.fetch_cmr_collections_metadata(
        concept_ids=["C123-TEST"],
        similarity_scores=[0.9],
        query_params={},
        page_size=10,
    )

    assert result.count == 1
    assert result.results[0].concept_id == "C123-TEST"
    assert result.results[0].title == "Test Dataset"
    assert result.results[0].abstract == "Test Abstract"

    mock_langfuse.update_current_trace.assert_called_with(
        tags=["cmr_success"],
        metadata={
            "collection_count": 1,
            "response_format": "json",
        },
    )


@patch.object(mod, "fetch_cmr_collections_metadata")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_collections_with_temporal_only_start(
    mock_db, mock_embedding_gen, mock_fetch_metadata
):
    """Test search with only start date in temporal input"""
    # Setup mocks
    mock_db.connect.return_value = None
    mock_db.search.return_value = []
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2]

    mock_fetch_metadata.return_value = CollectionsEmbeddingsOutput(results=[], count=0)

    # Create input with only start date
    temporal = MagicMock()
    temporal.StartDate = datetime(2020, 1, 1)
    temporal.EndDate = None

    query = MagicMock()
    query.query = "test query"
    query.page_num = 1
    query.page_size = 5
    query.spatial = None
    query.temporal = temporal

    result = mod.search_cmr_collections_embeddings(query)

    assert result["count"] == 0
    assert result["results"] == []


@patch.object(mod, "fetch_cmr_collections_metadata")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_collections_with_temporal_only_end(
    mock_db, mock_embedding_gen, mock_fetch_metadata
):
    """Test search with only end date in temporal input"""
    # Setup mocks
    mock_db.connect.return_value = None
    mock_db.search.return_value = []
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2]
    mock_fetch_metadata.return_value = CollectionsEmbeddingsOutput(results=[], count=0)

    # Create input with only end date
    temporal = MagicMock()
    temporal.StartDate = None
    temporal.EndDate = datetime(2020, 12, 31)

    query = MagicMock()
    query.query = "test query"
    query.page_num = 1
    query.page_size = 5
    query.spatial = None
    query.temporal = temporal

    result = mod.search_cmr_collections_embeddings(query)

    assert result["count"] == 0
    assert result["results"] == []


@patch.object(mod, "fetch_cmr_collections_metadata")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_collections_no_temporal_input(
    mock_db, mock_embedding_gen, mock_fetch_metadata
):
    """Test search with no temporal input"""
    # Setup mocks
    mock_db.connect.return_value = None
    mock_db.search.return_value = []
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2]
    mock_fetch_metadata.return_value = CollectionsEmbeddingsOutput(results=[], count=0)

    # Create input with no temporal
    query = MagicMock()
    query.query = "test query"
    query.page_num = 1
    query.page_size = 5
    query.spatial = None
    query.temporal = None

    result = mod.search_cmr_collections_embeddings(query)

    assert result["count"] == 0
    assert result["results"] == []


@patch.object(mod, "fetch_cmr_collections_metadata")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_collections_with_temporal_both_dates_none(
    mock_db, mock_embedding_gen, mock_fetch_metadata
):
    """Test search with temporal input but both dates are None"""
    # Setup mocks
    mock_db.connect.return_value = None
    mock_db.search.return_value = []
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2]
    mock_fetch_metadata.return_value = CollectionsEmbeddingsOutput(results=[], count=0)

    # Create input with temporal but both dates None
    temporal = MagicMock()
    temporal.StartDate = None
    temporal.EndDate = None

    query = MagicMock()
    query.query = "test query"
    query.page_num = 1
    query.page_size = 5
    query.spatial = None
    query.temporal = temporal

    result = mod.search_cmr_collections_embeddings(query)

    assert result["count"] == 0
    assert result["results"] == []


@patch.object(mod, "process_spatial_query")
@patch.object(mod, "fetch_cmr_collections_metadata")
@patch.object(mod, "embedding_generator")
@patch.object(mod, "db")
def test_search_collections_with_spatial_geometry(
    mock_db, mock_embedding_gen, mock_fetch_metadata, mock_process_spatial
):
    """Test search with spatial query that returns valid geometry"""
    # Setup mocks
    mock_db.connect.return_value = None
    mock_db.search.return_value = []
    mock_embedding_gen.generate_embedding.return_value = [0.1, 0.2]
    mock_fetch_metadata.return_value = CollectionsEmbeddingsOutput(results=[], count=0)

    # Mock process_spatial_query to return geometry
    mock_process_spatial.return_value = {"geometry": "POLYGON((0 0, 1 1, 1 0, 0 0))"}

    # Create input with spatial query
    spatial = MagicMock()
    spatial.success = True
    spatial.geometry = "POLYGON((0 0, 1 1, 1 0, 0 0))"

    query = MagicMock()
    query.query = "test query"
    query.page_num = 1
    query.page_size = 5
    query.spatial = spatial
    query.temporal = None

    result = mod.search_cmr_collections_embeddings(query)

    assert result["count"] == 0
    assert result["results"] == []

    # Verify that fetch_cmr_collections_metadata was called with geometry in query_params
    call_args = mock_fetch_metadata.call_args
    assert call_args[1]["query_params"]["geometry"] == "POLYGON((0 0, 1 1, 1 0, 0 0))"
