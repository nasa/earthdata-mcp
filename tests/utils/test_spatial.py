"""Tests for the spatial utility module."""

from util.spatial import (
    SpatialResolution,
    check_spatial_disambiguation,
    extract_spatial_resolution,
    group_by_spatial_resolution,
)


class TestExtractSpatialResolution:
    """Tests for extract_spatial_resolution function."""

    def test_extracts_gridded_resolution(self):
        """Test extraction from GriddedResolutions."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {
                            "GriddedResolutions": [
                                {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                            ]
                        }
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.x_dimension == 1
        assert result.y_dimension == 1
        assert result.unit == "Kilometers"
        assert result.meters == 1000

    def test_extracts_non_gridded_resolution(self):
        """Test extraction from NonGriddedResolutions."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {
                            "NonGriddedResolutions": [
                                {"XDimension": 500, "YDimension": 500, "Unit": "Meters"}
                            ]
                        }
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.x_dimension == 500
        assert result.unit == "Meters"
        assert result.meters == 500

    def test_handles_varies_resolution(self):
        """Test handling of 'Varies' special value."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {"VariesResolution": "Varies"}
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.unit == "Varies"
        assert result.meters == 0

    def test_handles_point_resolution(self):
        """Test handling of 'Point' special value."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {"PointResolution": "Point"}
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.unit == "Point"

    def test_returns_none_when_no_resolution(self):
        """Test returns None when no resolution field."""
        metadata = {
            "SpatialExtent": {"HorizontalSpatialDomain": {"ResolutionAndCoordinateSystem": {}}}
        }

        result = extract_spatial_resolution(metadata)

        assert result is None

    def test_returns_none_when_no_spatial_extent(self):
        """Test returns None when no SpatialExtent."""
        metadata = {}

        result = extract_spatial_resolution(metadata)

        assert result is None

    def test_prefers_gridded_over_non_gridded(self):
        """Test that GriddedResolutions is preferred."""
        metadata = {
            "SpatialExtent": {
                "HorizontalSpatialDomain": {
                    "ResolutionAndCoordinateSystem": {
                        "HorizontalDataResolution": {
                            "GriddedResolutions": [
                                {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                            ],
                            "NonGriddedResolutions": [
                                {"XDimension": 500, "YDimension": 500, "Unit": "Meters"}
                            ],
                        }
                    }
                }
            }
        }

        result = extract_spatial_resolution(metadata)

        assert result is not None
        assert result.x_dimension == 1
        assert result.unit == "Kilometers"


class TestSpatialResolutionStr:
    """Tests for SpatialResolution __str__ method."""

    def test_kilometers_display(self):
        """Test display for kilometers."""
        resolution = SpatialResolution(x_dimension=1, y_dimension=1, unit="Kilometers", meters=1000)
        assert str(resolution) == "1 km"

    def test_meters_display(self):
        """Test display for meters."""
        resolution = SpatialResolution(x_dimension=250, y_dimension=250, unit="Meters", meters=250)
        assert str(resolution) == "250 m"

    def test_degrees_display(self):
        """Test display for decimal degrees."""
        resolution = SpatialResolution(
            x_dimension=0.25, y_dimension=0.25, unit="Decimal Degrees", meters=27830
        )
        assert str(resolution) == "0.25 deg"


class TestGroupBySpatialResolution:
    """Tests for group_by_spatial_resolution function."""

    def test_groups_by_resolution(self):
        """Test grouping collections by resolution."""
        collections = [
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 250, "YDimension": 250, "Unit": "Meters"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
        ]

        groups = group_by_spatial_resolution(collections)

        assert len(groups) == 2
        assert len(groups["1 km"]) == 2
        assert len(groups["250 m"]) == 1

    def test_groups_none_for_missing_resolution(self):
        """Test that collections without resolution are grouped under None."""
        collections = [
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
            {"SpatialExtent": {}},
            {},
        ]

        groups = group_by_spatial_resolution(collections)

        assert len(groups) == 2
        assert len(groups["1 km"]) == 1
        assert len(groups[None]) == 2


class TestCheckSpatialDisambiguation:
    """Tests for check_spatial_disambiguation function."""

    def test_no_disambiguation_when_same_resolution(self):
        """Test no disambiguation needed when all have same resolution."""
        collections = [
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is False
        assert resolutions == ["1 km"]

    def test_disambiguation_when_different_resolutions(self):
        """Test disambiguation needed when different resolutions."""
        collections = [
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 250, "YDimension": 250, "Unit": "Meters"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 5, "YDimension": 5, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is True
        assert len(resolutions) == 3
        # Should be sorted by size (smallest first)
        assert resolutions[0] == "250 m"
        assert resolutions[1] == "1 km"
        assert resolutions[2] == "5 km"

    def test_ignores_varies_resolution(self):
        """Test that 'Varies' resolution is ignored for disambiguation."""
        collections = [
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {"VariesResolution": "Varies"}
                        }
                    }
                }
            },
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is False
        assert resolutions == ["1 km"]

    def test_no_disambiguation_when_no_resolutions(self):
        """Test no disambiguation when no collections have resolution."""
        collections = [
            {"SpatialExtent": {}},
            {},
        ]

        needs_disambiguation, resolutions = check_spatial_disambiguation(collections)

        assert needs_disambiguation is False
        assert resolutions == []

    def test_sorts_resolutions_by_size(self):
        """Test resolutions are sorted by size (smallest first)."""
        collections = [
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {
                                        "XDimension": 0.25,
                                        "YDimension": 0.25,
                                        "Unit": "Decimal Degrees",
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 250, "YDimension": 250, "Unit": "Meters"}
                                ]
                            }
                        }
                    }
                }
            },
            {
                "SpatialExtent": {
                    "HorizontalSpatialDomain": {
                        "ResolutionAndCoordinateSystem": {
                            "HorizontalDataResolution": {
                                "GriddedResolutions": [
                                    {"XDimension": 1, "YDimension": 1, "Unit": "Kilometers"}
                                ]
                            }
                        }
                    }
                }
            },
        ]

        _, resolutions = check_spatial_disambiguation(collections)

        # 250m < 1km < 0.25deg (~27km)
        assert resolutions == ["250 m", "1 km", "0.25 deg"]
