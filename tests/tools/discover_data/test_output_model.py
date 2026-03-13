"""Tests for discover_data output model export module."""

from models.tools.discover_data import DiscoverDataOutput
from tools.discover_data import output_model


def test_output_model_exports_discover_data_output():
    """Output model module should re-export DiscoverDataOutput in __all__."""
    assert output_model.DiscoverDataOutput is DiscoverDataOutput
    assert output_model.__all__ == ["DiscoverDataOutput"]
