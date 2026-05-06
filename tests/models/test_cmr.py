"""Tests for models.cmr."""

from datetime import datetime

from models.cmr import CollectionData, ConceptType, ExtractionResult, KMSTerm


def test_concept_type():
    """Test function."""
    assert ConceptType.COLLECTION == "collection"
    assert ConceptType.VARIABLE == "variable"
    assert ConceptType.CITATION == "citation"


def test_kms_term():
    """Test function."""
    term = KMSTerm(term="ocean", scheme="sciencekeywords")
    assert term.term == "ocean"
    assert term.scheme == "sciencekeywords"
    assert term.uuid is None
    assert term.definition is None


def test_extraction_result():
    """Test function."""
    res = ExtractionResult()
    assert res.kms_terms == []

    t = KMSTerm(term="ocean", scheme="sciencekeywords")
    res2 = ExtractionResult(kms_terms=[t])
    assert len(res2.kms_terms) == 1


def test_collection_data():
    """Test function."""
    now = datetime.now()
    cd = CollectionData(
        metadata={"id": "1"},
        enriched_metadata={"title": "Test"},
        temporal_start=now,
        temporal_end=None,
        is_ongoing=True,
        spatial_wkt="POLYGON((0 0, 1 1))",
        is_global=False,
    )
    assert cd.metadata["id"] == "1"
    assert cd.temporal_start == now
    assert cd.is_ongoing is True
