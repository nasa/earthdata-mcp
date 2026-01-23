"""Pytest configuration and fixtures."""

import json
import os
from pathlib import Path
from typing import Any

# Set test environment variables before any imports that might use them
os.environ.setdefault("REDIS_SSL", "false")
os.environ.setdefault("REDIS_HOST", "localhost")

# Disable OpenTelemetry during tests to prevent connection errors to localhost:3000
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

MOCKS_DIR = Path(__file__).parent / "mocks"

# Shared test data for spatial extent tests
GLOBAL_BOUNDING_BOX = {
    "WestBoundingCoordinate": -180.0,
    "EastBoundingCoordinate": 180.0,
    "NorthBoundingCoordinate": 90.0,
    "SouthBoundingCoordinate": -90.0,
}


def generate_spatial_resolution_metadata(
    x_dim: float, y_dim: float, unit: str, resolution_type: str = "GriddedResolutions"
) -> dict[str, Any]:
    """
    Build nested UMM-C spatial resolution metadata structure.

    Args:
        x_dim: X dimension value
        y_dim: Y dimension value
        unit: Unit string (e.g., "Kilometers", "Meters", "Decimal Degrees")
        resolution_type: "GriddedResolutions" or "NonGriddedResolutions"

    Returns:
        Nested metadata dict with SpatialExtent.HorizontalSpatialDomain...
    """
    return {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "ResolutionAndCoordinateSystem": {
                    "HorizontalDataResolution": {
                        resolution_type: [{"XDimension": x_dim, "YDimension": y_dim, "Unit": unit}]
                    }
                }
            }
        }
    }


def load_mock(category: str, name: str) -> dict:
    """Load a mock JSON file from tests/mocks/{category}/{name}.json"""
    path = MOCKS_DIR / category / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
