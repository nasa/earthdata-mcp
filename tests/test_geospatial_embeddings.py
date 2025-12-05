from tools.geospatial_embeddings.tool import natural_language_geocode


def test_returns_not_implemented():
    """Test that function returns NOT IMPLEMENTED YET."""
    result = natural_language_geocode(location="San Francisco Bay Area")
    assert result == {"result": "NOT IMPLEMENTED YET"}


def test_returns_not_implemented_empty_location():
    """Test with empty location."""
    result = natural_language_geocode(location="")
    assert result == {"result": "NOT IMPLEMENTED YET"}
