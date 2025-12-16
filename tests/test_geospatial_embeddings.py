import json
import pytest
from unittest.mock import patch, Mock
from tools.geospatial_embeddings.tool import (
    natural_language_geocode,
    get_from_cache,
    store_in_cache,
)


# Pytest fixtures
@pytest.fixture
def sample_geometry():
    """Sample polygon geometry object for testing."""
    mock_geom = Mock()
    # Use a polygon representing San Francisco Bay Area
    polygon_wkt = "POLYGON((-122.5150 37.7050, -122.3549 37.7050, -122.3549 37.8150, -122.5150 37.8150, -122.5150 37.7050))"
    mock_geom.__str__ = Mock(return_value=polygon_wkt)
    return mock_geom


@pytest.fixture
def sample_cache_data():
    """Sample cached data with polygon geometry for testing."""
    return {
        "geoLocation": "San Francisco Bay Area",
        "geometry": "POLYGON((-122.5150 37.7050, -122.3549 37.7050, -122.3549 37.8150, -122.5150 37.8150, -122.5150 37.7050))",
        "success": True,
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("tools.geospatial_embeddings.tool.redis_client") as mock:
        yield mock


@pytest.fixture
def mock_geocoder():
    """Mock geocoding function."""
    with patch("tools.geospatial_embeddings.tool.convert_text_to_geom") as mock:
        yield mock


class TestCacheOperations:
    """Test Redis Cache operations."""

    def test_get_from_cache_hit(self, mock_redis, sample_cache_data):
        """Test successful cache retrieval"""

        mock_redis.get.return_value = json.dumps(sample_cache_data)
        result = get_from_cache("San Francisco Bay Area")

        assert result == sample_cache_data
        mock_redis.get.assert_called_once()

    def test_get_from_cache_miss(self, mock_redis):
        """Test cache miss."""
        mock_redis.get.return_value = None

        result = get_from_cache("Unknown Metropolitan Area")

        assert result is None
        mock_redis.get.assert_called_once()

    def test_get_from_cache_redis_error(self, mock_redis):
        """Test cache retrieval with Redis error."""
        mock_redis.get.side_effect = Exception("Redis connection failed")

        result = get_from_cache("San Francisco Bay Area")

        assert result is None

    def test_store_in_cache_success(self, mock_redis):
        """Test successful cache storage with polygon geometry."""
        data = {
            "geoLocation": "Silicon Valley",
            "geometry": "POLYGON((-122.2000 37.3000, -121.8000 37.3000, -121.8000 37.5000, -122.2000 37.5000, -122.2000 37.3000))",
            "success": True,
        }

        store_in_cache("Silicon Valley", data, ttl=1800)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 1800
        assert json.loads(call_args[0][2]) == data

    def test_store_in_cache_default_ttl(self, mock_redis):
        """Test cache storage with default TTL."""
        data = {"geometry": "POLYGON((...))", "test": "data"}

        store_in_cache("location", data)

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 900  # Default TTL

    def test_store_in_cache_redis_error(self, mock_redis):
        """Test cache storage with Redis error."""
        mock_redis.setex.side_effect = Exception("Redis connection failed")

        # Should not raise exception
        store_in_cache("San Francisco Bay Area", {"test": "data"})


class TestNaturalLanguageGeocode:
    """Test the main geocoding function."""

    @pytest.mark.parametrize("location", ["", None])
    def test_empty_or_none_location(self, location):
        """Test with empty or None location."""
        result = natural_language_geocode(location)

        assert result["success"] is False
        assert "error" in result
        assert "No location query provided" in result["error"]

    def test_cache_hit(self, sample_cache_data):
        """Test successful cache hit with polygon geometry."""
        with patch("tools.geospatial_embeddings.tool.get_from_cache") as mock_get_cache:
            mock_get_cache.return_value = sample_cache_data

            result = natural_language_geocode("San Francisco Bay Area")

            assert result["from_cache"] is True
            assert result["success"] is True
            assert result["geoLocation"] == "San Francisco Bay Area"
            assert "POLYGON" in result["geometry"]
            mock_get_cache.assert_called_once_with("San Francisco Bay Area")

    def test_cache_miss_successful_geocoding(self, sample_geometry):
        """Test cache miss with successful geocoding returning polygon."""
        with (
            patch("tools.geospatial_embeddings.tool.get_from_cache") as mock_get_cache,
            patch("tools.geospatial_embeddings.tool.store_in_cache") as mock_store,
            patch(
                "tools.geospatial_embeddings.tool.convert_text_to_geom"
            ) as mock_convert,
        ):

            mock_get_cache.return_value = None  # Cache miss
            mock_convert.return_value = sample_geometry

            result = natural_language_geocode("Silicon Valley")

            assert result["success"] is True
            assert result["geoLocation"] == "Silicon Valley"
            assert "POLYGON" in result["geometry"]
            assert result["geometry"].startswith("POLYGON")

            mock_get_cache.assert_called_once_with("Silicon Valley")
            mock_convert.assert_called_once_with("Silicon Valley")
            mock_store.assert_called_once()

    def test_cache_miss_failed_geocoding(self):
        """Test cache miss with failed geocoding."""
        with (
            patch("tools.geospatial_embeddings.tool.get_from_cache") as mock_get_cache,
            patch(
                "tools.geospatial_embeddings.tool.convert_text_to_geom"
            ) as mock_convert,
        ):

            mock_get_cache.return_value = None  # Cache miss
            mock_convert.return_value = None  # Geocoding failed

            result = natural_language_geocode("Nonexistent Metropolitan Area XYZ123")

            assert result["success"] is False
            assert "error" in result
            assert "Unable to geocode" in result["error"]
            assert "Nonexistent Metropolitan Area XYZ123" in result["error"]

    def test_geocoding_exception(self):
        """Test exception during geocoding."""
        with (
            patch("tools.geospatial_embeddings.tool.get_from_cache") as mock_get_cache,
            patch(
                "tools.geospatial_embeddings.tool.convert_text_to_geom"
            ) as mock_convert,
        ):

            mock_get_cache.return_value = None  # Cache miss
            mock_convert.side_effect = Exception("Geocoding API Error")

            result = natural_language_geocode("San Francisco Bay Area")

            assert result["success"] is False
            assert "error" in result
            assert "Exception during geocoding" in result["error"]
            assert "Geocoding API Error" in result["error"]
