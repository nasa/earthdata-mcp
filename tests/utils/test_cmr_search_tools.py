"""Tests for util.cmr.search_tools helpers."""

import pytest

from util.cmr.search_tools import build_spatial_files


def test_build_spatial_files_raises_value_error_for_invalid_wkt():
    """Malformed WKT should be normalized to ValueError."""
    with pytest.raises(ValueError, match="Invalid WKT geometry"):
        build_spatial_files("POINT((1 2))")
