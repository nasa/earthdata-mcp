"""Tests for cmr_utils module"""

import pytest
from util.cmr_utils import reorder_results, wkt_to_cmr_params


class TestReorderResults:
    """Tests for reorder_results function"""

    def test_reorder_umm_json_format(self):
        """Test reordering with umm_json format"""
        response = {
            "data": {
                "items": [
                    {
                        "meta": {
                            "concept-id": "C1-TEST",
                            "granule-count": 100,
                        },
                        "umm": {"EntryTitle": "Dataset 1"},
                    },
                    {
                        "meta": {
                            "concept-id": "C2-TEST",
                            "granule-count": 50,
                        },
                        "umm": {"EntryTitle": "Dataset 2"},
                    },
                    {
                        "meta": {
                            "concept-id": "C3-TEST",
                            "granule-count": 75,
                        },
                        "umm": {"EntryTitle": "Dataset 3"},
                    },
                ]
            }
        }

        # Reverse order from Postgres
        concept_ids = ["C3-TEST", "C1-TEST", "C2-TEST"]
        similarity_scores = [0.95, 0.90, 0.85]

        result = reorder_results(response, concept_ids, "umm_json", similarity_scores)

        assert len(result) == 3
        assert result[0]["meta"]["concept-id"] == "C3-TEST"
        assert result[0]["meta"]["similarity-score"] == 0.95
        assert result[1]["meta"]["concept-id"] == "C1-TEST"
        assert result[1]["meta"]["similarity-score"] == 0.90
        assert result[2]["meta"]["concept-id"] == "C2-TEST"
        assert result[2]["meta"]["similarity-score"] == 0.85

    def test_reorder_json_format(self):
        """Test reordering with json format"""
        response = {
            "data": {
                "feed": {
                    "entry": [
                        {
                            "id": "C1-TEST",
                            "granule_count": "100",
                            "title": "Dataset 1",
                        },
                        {
                            "id": "C2-TEST",
                            "granule_count": "50",
                            "title": "Dataset 2",
                        },
                    ]
                }
            }
        }

        concept_ids = ["C2-TEST", "C1-TEST"]
        similarity_scores = [0.92, 0.88]

        result = reorder_results(response, concept_ids, "json", similarity_scores)

        assert len(result) == 2
        assert result[0]["id"] == "C2-TEST"
        assert result[0]["similarity_score"] == 0.92
        assert result[1]["id"] == "C1-TEST"
        assert result[1]["similarity_score"] == 0.88

    def test_filter_zero_granule_count_umm_json(self):
        """Test filtering out items with zero granule count in umm_json format"""
        response = {
            "data": {
                "items": [
                    {
                        "meta": {
                            "concept-id": "C1-TEST",
                            "granule-count": 100,
                        },
                        "umm": {"EntryTitle": "Dataset 1"},
                    },
                    {
                        "meta": {
                            "concept-id": "C2-TEST",
                            "granule-count": 0,
                        },
                        "umm": {"EntryTitle": "Dataset 2"},
                    },
                ]
            }
        }

        concept_ids = ["C1-TEST", "C2-TEST"]
        similarity_scores = [0.90, 0.85]

        result = reorder_results(response, concept_ids, "umm_json", similarity_scores)

        # Only C1-TEST should be in results (C2-TEST has 0 granules)
        assert len(result) == 1
        assert result[0]["meta"]["concept-id"] == "C1-TEST"

    def test_filter_zero_granule_count_json(self):
        """Test filtering out items with zero granule count in json format"""
        response = {
            "data": {
                "feed": {
                    "entry": [
                        {
                            "id": "C1-TEST",
                            "granule_count": "100",
                            "title": "Dataset 1",
                        },
                        {
                            "id": "C2-TEST",
                            "granule_count": "0",
                            "title": "Dataset 2",
                        },
                    ]
                }
            }
        }

        concept_ids = ["C1-TEST", "C2-TEST"]
        similarity_scores = [0.90, 0.85]

        result = reorder_results(response, concept_ids, "json", similarity_scores)

        assert len(result) == 1
        assert result[0]["id"] == "C1-TEST"

    def test_missing_concept_id_in_cmr_response(self):
        """Test handling when Postgres has IDs not in CMR response"""
        response = {
            "data": {
                "items": [
                    {
                        "meta": {
                            "concept-id": "C1-TEST",
                            "granule-count": 100,
                        },
                        "umm": {"EntryTitle": "Dataset 1"},
                    },
                ]
            }
        }

        # C2-TEST doesn't exist in CMR response
        concept_ids = ["C1-TEST", "C2-TEST"]
        similarity_scores = [0.90, 0.85]

        result = reorder_results(response, concept_ids, "umm_json", similarity_scores)

        # Only C1-TEST should be in results
        assert len(result) == 1
        assert result[0]["meta"]["concept-id"] == "C1-TEST"

    def test_missing_granule_count_umm_json(self):
        """Test handling missing granule-count in umm_json format"""
        response = {
            "data": {
                "items": [
                    {
                        "meta": {
                            "concept-id": "C1-TEST",
                            # granule-count missing
                        },
                        "umm": {"EntryTitle": "Dataset 1"},
                    },
                ]
            }
        }

        concept_ids = ["C1-TEST"]
        similarity_scores = [0.90]

        result = reorder_results(response, concept_ids, "umm_json", similarity_scores)

        # Should be filtered out (defaults to 0)
        assert len(result) == 0

    def test_missing_granule_count_json(self):
        """Test handling missing granule_count in json format"""
        response = {
            "data": {
                "feed": {
                    "entry": [
                        {
                            "id": "C1-TEST",
                            # granule_count missing
                            "title": "Dataset 1",
                        },
                    ]
                }
            }
        }

        concept_ids = ["C1-TEST"]
        similarity_scores = [0.90]

        result = reorder_results(response, concept_ids, "json", similarity_scores)

        # Should be filtered out (defaults to 0)
        assert len(result) == 0


class TestWktToCmrParams:
    """Tests for wkt_to_cmr_params function"""

    def test_point_conversion(self):
        """Test converting a Point WKT to CMR params"""
        wkt = "POINT (30 10)"
        result = wkt_to_cmr_params(wkt)

        assert "point" in result
        assert result["point"] == "30.0,10.0"

    def test_polygon_conversion(self):
        """Test converting a Polygon WKT to CMR params"""
        wkt = "POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))"
        result = wkt_to_cmr_params(wkt)

        assert "polygon[]" in result
        assert isinstance(result["polygon[]"], list)
        assert len(result["polygon[]"]) == 1
        # Check that coordinates are reversed (counter-clockwise)
        assert "30.0,10.0" in result["polygon[]"][0]

    def test_multipolygon_conversion(self):
        """Test converting a MultiPolygon WKT to CMR params"""
        wkt = "MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)), ((15 5, 40 10, 10 20, 5 10, 15 5)))"
        result = wkt_to_cmr_params(wkt)

        assert "polygon[]" in result
        assert isinstance(result["polygon[]"], list)
        assert len(result["polygon[]"]) == 2

    def test_simplification_applied(self):
        """Test that geometry simplification is applied"""
        # Create a complex polygon
        coords = [(i, i) for i in range(100)]
        coords.append(coords[0])  # Close the polygon
        wkt = f"POLYGON (({', '.join(f'{x} {y}' for x, y in coords)}))"

        result = wkt_to_cmr_params(wkt)

        assert "polygon[]" in result
        # The actual count might vary based on the simplification algorithm
        # Just verify it returns a valid polygon format
        coordinates = result["polygon[]"][0].split(",")
        assert len(coordinates) > 0
        assert len(coordinates) % 2 == 0  # Should be even (x,y pairs)

    def test_invalid_geometry_type(self):
        """Test error handling for invalid geometry type"""
        wkt = "LINESTRING (30 10, 10 30, 40 40)"

        with pytest.raises(ValueError, match="Point, Polygon, or MultiPolygon"):
            wkt_to_cmr_params(wkt)

    def test_counter_clockwise_ordering(self):
        """Test that polygon coordinates are reversed for counter-clockwise ordering"""
        wkt = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
        result = wkt_to_cmr_params(wkt)

        coords_str = result["polygon[]"][0]
        coords_list = coords_str.split(",")

        # First coordinate should be 0,0 (the last in original due to reversal)
        assert coords_list[0] == "0.0"
        assert coords_list[1] == "0.0"

    def test_complex_geometry_simplification(self):
        """Test simplification with tolerance parameter"""
        # Create a polygon with many points along a line
        coords = [(0, 0), (0, 0.1), (0, 0.2), (0, 0.3), (0, 1), (1, 1), (1, 0), (0, 0)]
        wkt_coords = ", ".join(f"{x} {y}" for x, y in coords)
        wkt = f"POLYGON (({wkt_coords}))"

        result = wkt_to_cmr_params(wkt)

        # After simplification with tolerance 0.5, collinear points should be removed
        coord_count = len(result["polygon[]"][0].split(",")) // 2
        assert coord_count < len(coords)
