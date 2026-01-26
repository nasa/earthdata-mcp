"""Tests for extract_spatial_constraint implementation with mocked dependencies."""

from unittest.mock import MagicMock, patch

import pytest

from tools.discover_data.input_model import SpatialConstraint
from tools.discover_data.utils import extract_spatial_constraint


@pytest.fixture(autouse=True)
def stub_external_clients(monkeypatch):
    """Disable real client initialization during tests."""
    monkeypatch.setattr("tools.discover_data.utils.extract_spatial_constraint.LANGFUSE", None)
    monkeypatch.setattr("tools.discover_data.utils.extract_spatial_constraint.cache", None)


class TestExtractSpatialWithLLM:
    """Test the _extract_spatial_with_llm helper function."""

    def test_successful_extraction(self):
        """LLM extraction should return SpatialExtractionResult with location info."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_spatial_constraint.Path"),
            patch("builtins.open", create=True) as mock_file,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_file.return_value.__enter__.return_value.read.return_value = "System prompt"

            # Mock response with string values (not MagicMock to avoid buffer issues)
            mock_response = MagicMock()
            mock_response.location_name = "Colorado"
            mock_response.location_with_context = "State of Colorado, USA"
            mock_response.reasoning = "US state identified"
            mock_client.create.return_value = mock_response

            result = extract_spatial_constraint._extract_spatial_with_llm("data from Colorado")

            assert result is not None
            assert result.location_name == "Colorado"
            assert result.location_with_context == "State of Colorado, USA"
            assert result.reasoning == "US state identified"

    def test_no_location_in_response(self):
        """LLM extraction should return None when location not found."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_spatial_constraint.Path"),
            patch("builtins.open", create=True) as mock_file,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_file.return_value.__enter__.return_value.read.return_value = "System prompt"

            # Mock response with empty location
            mock_response = MagicMock()
            mock_response.location_name = None
            mock_response.location_with_context = None
            mock_response.reasoning = None
            mock_client.create.return_value = mock_response

            result = extract_spatial_constraint._extract_spatial_with_llm("no location here")

            assert result is None

    def test_llm_error_propagates(self):
        """LLM extraction should propagate errors from LLM."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_spatial_constraint.Path"),
            patch("builtins.open", create=True) as mock_file,
        ):
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_file.return_value.__enter__.return_value.read.return_value = "System prompt"
            mock_client.create.side_effect = ValueError("LLM API error")

            with pytest.raises(RuntimeError, match="Failed to extract spatial info from query"):
                extract_spatial_constraint._extract_spatial_with_llm("invalid query")

    def test_client_init_error_propagates(self):
        """Client initialization errors should propagate."""
        with patch("tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider") as mock_instructor:
            mock_instructor.side_effect = ConnectionError("Cannot connect to Bedrock")

            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_spatial_constraint._extract_spatial_with_llm("test query")


class TestExtractSpatialConstraintWrapper:
    """Test the extract_spatial_constraint wrapper function."""

    def test_successful_extraction_with_geocoding(self):
        """Wrapper should extract location and geocode it."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache", None),
        ):
            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Denver"
            mock_llm_result.location_with_context = "Denver, Colorado"
            mock_llm_result.reasoning = "Identified city name"
            mock_llm_result.cache_key = "denver_cache_key"
            mock_llm.return_value = mock_llm_result

            # Mock geocoding result
            mock_geocode.return_value = "POLYGON((...))"

            result = extract_spatial_constraint.extract_spatial_constraint("data from Denver")

            assert result.location == "Denver, Colorado"
            assert result.wkt_geometry == "POLYGON((...))"
            assert result.reasoning == "Identified city name"
            mock_llm.assert_called_once()
            mock_geocode.assert_called_once_with("Denver, Colorado")

    def test_empty_query_returns_no_location(self):
        """Empty query should return SpatialConstraint with no location."""
        with patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm:
            result = extract_spatial_constraint.extract_spatial_constraint("")

            assert result.location is None
            assert result.wkt_geometry is None
            mock_llm.assert_not_called()

    def test_none_query_returns_no_location(self):
        """None query should return SpatialConstraint with no location."""
        with patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm:
            result = extract_spatial_constraint.extract_spatial_constraint(None)

            assert result.location is None
            assert result.wkt_geometry is None
            mock_llm.assert_not_called()

    def test_llm_returns_none(self):
        """When LLM returns None, should return SpatialConstraint with reasoning."""
        with patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm:
            mock_llm.return_value = None

            result = extract_spatial_constraint.extract_spatial_constraint("some query")

            assert result.location is None
            assert result.wkt_geometry is None
            assert result.reasoning == "No spatial information found in query"

    def test_geocoding_fails(self):
        """When geocoding fails, should return location but no geometry."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache", None),
        ):
            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Invalid Place"
            mock_llm_result.location_with_context = "Invalid Place XYZ"
            mock_llm_result.reasoning = "Location extraction"
            mock_llm_result.cache_key = "invalid_key"
            mock_llm.return_value = mock_llm_result

            # Mock geocoding failure
            mock_geocode.return_value = None

            result = extract_spatial_constraint.extract_spatial_constraint("data from Invalid Place XYZ")

            assert result.location == "Invalid Place XYZ"
            assert result.wkt_geometry is None
            assert result.reasoning == "Location extraction"

    def test_geocoding_validation_error(self):
        """When geocoding raises ValueError, should return location but no geometry."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache", None),
        ):
            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Test Location"
            mock_llm_result.location_with_context = "Test Location"
            mock_llm_result.reasoning = "Extracted"
            mock_llm_result.cache_key = "test_key"
            mock_llm.return_value = mock_llm_result

            # Mock geocoding error
            mock_geocode.side_effect = ValueError("Invalid format")

            result = extract_spatial_constraint.extract_spatial_constraint("data from Test Location")

            assert result.location == "Test Location"
            assert result.wkt_geometry is None
            assert result.reasoning == "Extracted"

    def test_geocoding_generic_error(self):
        """When geocoding raises generic exception, should return location but no geometry."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache", None),
        ):
            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Test Location"
            mock_llm_result.location_with_context = "Test Location"
            mock_llm_result.reasoning = "Extracted"
            mock_llm_result.cache_key = "test_key"
            mock_llm.return_value = mock_llm_result

            # Mock geocoding error
            mock_geocode.side_effect = Exception("API error")

            result = extract_spatial_constraint.extract_spatial_constraint("data from Test Location")

            assert result.location == "Test Location"
            assert result.wkt_geometry is None
            assert result.reasoning == "Extracted"

    def test_cache_hit(self):
        """When result is in cache, should not call geocoding."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
        ):
            # Create a mock cache
            mock_cache = MagicMock()
            mock_cache.get.return_value = "POLYGON((cached))"

            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Denver"
            mock_llm_result.location_with_context = "Denver"
            mock_llm_result.reasoning = "Cached"
            mock_llm_result.cache_key = "denver_key"
            mock_llm.return_value = mock_llm_result

            # Patch the cache at the module level
            with patch("tools.discover_data.utils.extract_spatial_constraint.cache", mock_cache):
                result = extract_spatial_constraint.extract_spatial_constraint("data from Denver")

                assert result.location == "Denver"
                assert result.wkt_geometry == "POLYGON((cached))"
                assert "cached" in result.reasoning
                # Geocoding should not be called because it was cached
                mock_geocode.assert_not_called()
                mock_cache.get.assert_called()

    def test_cache_miss_stores_result(self):
        """When geocoding succeeds, should store result in cache."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
        ):
            # Create a mock cache
            mock_cache = MagicMock()
            mock_cache.get.return_value = None  # Cache miss

            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Denver"
            mock_llm_result.location_with_context = "Denver, CO"
            mock_llm_result.reasoning = "City"
            mock_llm_result.cache_key = "denver_key"
            mock_llm.return_value = mock_llm_result

            # Mock geocoding result
            mock_geocode.return_value = "POLYGON((...))"

            # Patch the cache at the module level
            with patch("tools.discover_data.utils.extract_spatial_constraint.cache", mock_cache):
                result = extract_spatial_constraint.extract_spatial_constraint("data from Denver")

                assert result.location == "Denver, CO"
                assert result.wkt_geometry == "POLYGON((...))"
                # Should store in cache
                mock_cache.set.assert_called()

    def test_cache_disabled(self):
        """When cache is None, should skip caching operations."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint._extract_spatial_with_llm") as mock_llm,
            patch("tools.discover_data.utils.extract_spatial_constraint.convert_text_to_geom") as mock_geocode,
            patch("tools.discover_data.utils.extract_spatial_constraint.cache", None),
        ):
            # Mock LLM result
            mock_llm_result = MagicMock()
            mock_llm_result.location_name = "Denver"
            mock_llm_result.location_with_context = "Denver, CO"
            mock_llm_result.reasoning = "City"
            mock_llm_result.cache_key = "denver_key"
            mock_llm.return_value = mock_llm_result

            # Mock geocoding result
            mock_geocode.return_value = "POLYGON((...))"

            result = extract_spatial_constraint.extract_spatial_constraint("data from Denver")

            assert result.location == "Denver, CO"
            assert result.wkt_geometry == "POLYGON((...))"
            # Geocoding should be called
            mock_geocode.assert_called_once()


class TestExtractSpatialInitialization:
    """Test module-level initialization and error handling."""

    def test_instructor_client_initialization_error(self):
        """Instructor client initialization failure should be caught."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_spatial_constraint.LANGFUSE", None),
        ):
            mock_instructor.side_effect = RuntimeError("Bedrock service unavailable")
            
            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_spatial_constraint._extract_spatial_with_llm("test query")

    def test_langfuse_error_handling_when_available(self):
        """When Langfuse is available, errors should be logged to it."""
        with (
            patch("tools.discover_data.utils.extract_spatial_constraint.instructor.from_provider") as mock_instructor,
            patch("tools.discover_data.utils.extract_spatial_constraint.LANGFUSE") as mock_langfuse,
        ):
            mock_langfuse.update_current_trace = MagicMock()
            mock_instructor.side_effect = ValueError("Bedrock error")
            
            with pytest.raises(RuntimeError, match="Failed to initialize instructor client"):
                extract_spatial_constraint._extract_spatial_with_llm("test query")
            
            # Verify Langfuse was called to log the error
            assert mock_langfuse.update_current_trace.called

    def test_spatial_extraction_result_cache_key_generation(self):
        """SpatialExtractionResult should properly generate cache keys."""
        result = extract_spatial_constraint.SpatialExtractionResult(
            location_name="Denver",
            location_with_context="Denver, CO",
            reasoning="City",
        )
        
        assert result.location_name == "Denver"
        assert result.location_with_context == "Denver, CO"
        assert result.reasoning == "City"
        assert result.cache_key is not None
        assert result.cache_key.startswith("geocode:")

    def test_spatial_extraction_result_no_cache_key_for_none_location(self):
        """SpatialExtractionResult should not generate cache key for None location."""
        result = extract_spatial_constraint.SpatialExtractionResult(
            location_name=None,
            location_with_context="Some Place",
            reasoning="No location",
        )
        
        assert result.cache_key is None

    def test_cache_key_normalization(self):
        """Cache keys should normalize location names consistently."""
        result1 = extract_spatial_constraint.SpatialExtractionResult(
            location_name="Denver",
            location_with_context="Denver, CO",
            reasoning="City",
        )
        
        result2 = extract_spatial_constraint.SpatialExtractionResult(
            location_name="DENVER",
            location_with_context="Denver, CO",
            reasoning="City",
        )
        
        # Both should generate the same cache key (case-insensitive)
        assert result1.cache_key == result2.cache_key
