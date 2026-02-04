"""Models subpackage - re-exports from parent models.py module for backward compatibility."""

# Re-export all models from the sibling models.py file
# We need to import from the parent's models.py, not this __init__.py
import importlib.util
from pathlib import Path

from util.models.natural_language_geocoder import ValidationError

# Load models.py from parent directory
_models_path = Path(__file__).parent.parent / "models.py"
_spec = importlib.util.spec_from_file_location("_util_models", _models_path)
_models_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_models_module)

# Re-export all the model classes
CollectionData = _models_module.CollectionData
ConceptMessage = _models_module.ConceptMessage
ConceptType = _models_module.ConceptType
EmbeddingChunk = _models_module.EmbeddingChunk
ExtractionResult = _models_module.ExtractionResult
KMSTerm = _models_module.KMSTerm

__all__ = [
    "CollectionData",
    "ConceptMessage",
    "ConceptType",
    "EmbeddingChunk",
    "ExtractionResult",
    "KMSTerm",
    "ValidationError",
]
