"""Test for geospatial embeddings utility"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from tools.discover_data.utils.extract_spatial_constraint import extract_spatial_constraint


# Pytest fixtures
@pytest.fixture
def sample_geometry():
    """Sample polygon geometry object for testing."""
    mock_geom = Mock()
    # Use a polygon representing San Francisco Bay Area
    polygon_wkt = (
        "POLYGON((-122.5150 37.7050, -122.3549 37.7050, -122.3549 37.8150, "
        "-122.5150 37.8150, -122.5150 37.7050))"
    )
    mock_geom.__str__ = Mock(return_value=polygon_wkt)
    return mock_geom


@pytest.fixture
def sample_cache_data():
    """Sample cached data with polygon geometry for testing."""
    return {
        "geometry": (
            "POLYGON((-122.5150 37.7050, -122.3549 37.7050, -122.3549 37.8150, "
            "-122.5150 37.8150, -122.5150 37.7050))"
        ),
    }


class TestExtractSpatialConstraint:
    """Test the main geospatial constraint extraction function."""

    @pytest.mark.parametrize("location", ["", None])
    def test_empty_or_none_location(self, location):
        """Test with empty or None location."""

        result = extract_spatial_constraint(location)
        # Empty strings are treated as None by the utility
        assert result.location is None
        assert result.wkt_geometry is None

    def test_successful_geocoding(self, sample_geometry):
        """Test successful geocoding returning polygon."""
        with (
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.extract_spatial_with_llm"
            ) as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache") as mock_cache,
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom"
            ) as mock_convert,
        ):
            # Mock the LLM to return extracted spatial info
            mock_result = MagicMock()
            mock_result.location_name = "San Francisco Bay Area"
            mock_result.location_with_context = "San Francisco Bay Area"
            mock_result.reasoning = "Extracted from query"
            mock_result.cache_key = "test_key"
            mock_llm.return_value = mock_result

            mock_cache.get.return_value = None  # Cache miss
            mock_convert.return_value = sample_geometry
            mock_cache.set.return_value = True

            result = extract_spatial_constraint("San Francisco Bay Area")

            assert result.location == "San Francisco Bay Area"
            assert result.wkt_geometry is not None
            assert "POLYGON" in result.wkt_geometry
            mock_convert.assert_called_once_with("San Francisco Bay Area")
            mock_cache.set.assert_called_once()

    def test_cache_hit(self, sample_cache_data):
        """Test successful cache hit with polygon geometry."""
        with (
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.extract_spatial_with_llm"
            ) as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache") as mock_cache,
        ):
            # Mock the LLM to return extracted spatial info
            mock_result = MagicMock()
            mock_result.location_name = "San Francisco Bay Area"
            mock_result.location_with_context = "San Francisco Bay Area"
            mock_result.reasoning = "Extracted from query"
            mock_result.cache_key = "test_key"
            mock_llm.return_value = mock_result

            # The geospatial utility stores the geometry string directly in cache
            # (not wrapped in a dict)
            cached_geometry = sample_cache_data["geometry"]
            mock_cache.get.return_value = cached_geometry

            result = extract_spatial_constraint("San Francisco Bay Area")

            assert result.location == "San Francisco Bay Area"
            assert result.wkt_geometry == cached_geometry
            mock_cache.get.assert_called_once()

    def test_failed_geocoding(self):
        """Test failed geocoding."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint.cache") as mock_cache,
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom"
            ) as mock_convert,
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.extract_spatial_with_llm"
            ) as mock_llm,
        ):
            mock_cache.get.return_value = None  # Cache miss
            mock_convert.return_value = None  # Geocoding failed
            # Mock the LLM to return a result with location
            mock_result = MagicMock()
            mock_result.location_name = "Nonexistent Metropolitan Area XYZ123"
            mock_result.location_with_context = "Nonexistent Metropolitan Area XYZ123"
            mock_result.reasoning = "Extracted from query"
            mock_result.cache_key = "test_key"
            mock_llm.return_value = mock_result

            result = extract_spatial_constraint("Nonexistent Metropolitan Area XYZ123")

            assert result.location == "Nonexistent Metropolitan Area XYZ123"
            assert result.wkt_geometry is None

    def test_geocoding_value_error_exception(self):
        """Test ValueError exception during geocoding."""
        with (
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.extract_spatial_with_llm"
            ) as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache") as mock_cache,
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom"
            ) as mock_convert,
        ):
            # Mock the LLM to return extracted spatial info
            mock_result = MagicMock()
            mock_result.location_name = "San Francisco Bay Area"
            mock_result.location_with_context = "San Francisco Bay Area"
            mock_result.reasoning = "Extracted from query"
            mock_result.cache_key = "test_key"
            mock_llm.return_value = mock_result

            mock_cache.get.return_value = None  # Cache miss
            mock_convert.side_effect = ValueError("Invalid parameter format")

            result = extract_spatial_constraint("San Francisco Bay Area")

            assert result.location == "San Francisco Bay Area"
            assert result.wkt_geometry is None

    def test_geocoding_type_error_exception(self):
        """Test TypeError exception during geocoding."""
        with (
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.extract_spatial_with_llm"
            ) as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache") as mock_cache,
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom"
            ) as mock_convert,
        ):
            # Mock the LLM to return extracted spatial info
            mock_result = MagicMock()
            mock_result.location_name = "San Francisco Bay Area"
            mock_result.location_with_context = "San Francisco Bay Area"
            mock_result.reasoning = "Extracted from query"
            mock_result.cache_key = "test_key"
            mock_llm.return_value = mock_result

            mock_cache.get.return_value = None  # Cache miss
            mock_convert.side_effect = TypeError("Expected string, got int")

            result = extract_spatial_constraint("San Francisco Bay Area")

            assert result.location == "San Francisco Bay Area"
            assert result.wkt_geometry is None

    def test_geocoding_generic_exception(self):
        """Test generic exception during geocoding."""
        with (
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.extract_spatial_with_llm"
            ) as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache") as mock_cache,
            patch(
                "tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom"
            ) as mock_convert,
        ):
            # Mock the LLM to return extracted spatial info
            mock_result = MagicMock()
            mock_result.location_name = "San Francisco Bay Area"
            mock_result.location_with_context = "San Francisco Bay Area"
            mock_result.reasoning = "Extracted from query"
            mock_result.cache_key = "test_key"
            mock_llm.return_value = mock_result

            mock_cache.get.return_value = None  # Cache miss
            mock_convert.side_effect = Exception("Geocoding API Error")

            result = extract_spatial_constraint("San Francisco Bay Area")

            assert result.location == "San Francisco Bay Area"
            assert result.wkt_geometry is None
