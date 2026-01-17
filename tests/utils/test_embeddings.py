"""Tests for embedding generators."""

from unittest.mock import MagicMock, patch

import pytest

from util.embeddings import (
    BedrockEmbeddingGenerator,
    KMSEnrichedEmbeddingGenerator,
    RoutingEmbeddingGenerator,
    get_embedding_generator,
)
from util.kms import clear_cache as kms_clear_cache
from util.models import KMSTerm


class TestKMSEnrichedEmbeddingGenerator:
    """Tests for KMSEnrichedEmbeddingGenerator."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the KMS cache between tests."""
        kms_clear_cache()
        yield
        kms_clear_cache()

    @pytest.fixture
    def mock_base_generator(self):
        """Create a mock base generator."""
        mock = MagicMock(spec=BedrockEmbeddingGenerator)
        mock.model_id = "test-model"
        mock.generate.return_value = [0.1] * 1024
        return mock

    @pytest.fixture
    def generator(self, mock_base_generator):
        """Create a KMSEnrichedEmbeddingGenerator with mocked base."""
        return KMSEnrichedEmbeddingGenerator(mock_base_generator)

    def test_delegates_model_id(self, generator):
        """Should delegate model_id to base generator."""
        assert generator.model_id == "test-model"

    def test_enriches_single_keyword(self, generator, mock_base_generator):
        """Should enrich a single keyword path with definition."""
        mock_term = KMSTerm(
            uuid="abc-123",
            scheme="sciencekeywords",
            term="PRECIPITATION",
            definition="Water falling from clouds",
        )
        with patch("util.embeddings.kms.lookup_term", return_value=mock_term):
            generator.generate(
                "EARTH SCIENCE > ATMOSPHERE > PRECIPITATION",
                concept_type="collection",
                attribute="science_keywords",
            )

            # Should have called base with enriched text
            call_args = mock_base_generator.generate.call_args
            enriched_text = call_args[0][0]
            assert "PRECIPITATION: Water falling from clouds" in enriched_text

    def test_enriches_multiple_keywords(self, generator, mock_base_generator):
        """Should enrich multiple keyword paths."""
        mock_terms = [
            KMSTerm(
                uuid="abc-123",
                scheme="sciencekeywords",
                term="PRECIPITATION",
                definition="Water falling",
            ),
            KMSTerm(
                uuid="def-456",
                scheme="sciencekeywords",
                term="WIND",
                definition="Air movement",
            ),
        ]
        with patch("util.embeddings.kms.lookup_term", side_effect=mock_terms):
            generator.generate(
                "EARTH SCIENCE > ATMOSPHERE > PRECIPITATION\nEARTH SCIENCE > ATMOSPHERE > WIND",
                concept_type="collection",
                attribute="science_keywords",
            )

            call_args = mock_base_generator.generate.call_args
            enriched_text = call_args[0][0]
            assert "PRECIPITATION: Water falling" in enriched_text
            assert "WIND: Air movement" in enriched_text

    def test_fallback_on_definition_not_found(self, generator, mock_base_generator):
        """Should fall back to original path if no definition found."""
        with patch("util.embeddings.kms.lookup_term", return_value=None):
            generator.generate(
                "EARTH SCIENCE > ATMOSPHERE > UNKNOWN_TERM",
                concept_type="collection",
                attribute="science_keywords",
            )

            call_args = mock_base_generator.generate.call_args
            enriched_text = call_args[0][0]
            # Should contain original path since no definition found
            assert "EARTH SCIENCE > ATMOSPHERE > UNKNOWN_TERM" in enriched_text

    def test_fallback_on_fetch_exception(self, generator, mock_base_generator):
        """Should fall back to original path if fetch fails."""
        with patch(
            "util.embeddings.kms.lookup_term",
            side_effect=Exception("Network error"),
        ):
            generator.generate(
                "EARTH SCIENCE > ATMOSPHERE > PRECIPITATION",
                concept_type="collection",
                attribute="science_keywords",
            )

            call_args = mock_base_generator.generate.call_args
            enriched_text = call_args[0][0]
            # Should contain original path since fetch failed
            assert "EARTH SCIENCE > ATMOSPHERE > PRECIPITATION" in enriched_text

    def test_extract_term_hierarchical(self, generator):
        """Should extract last segment from hierarchical paths."""
        assert generator._extract_term("A > B > C") == "C"
        assert generator._extract_term("EARTH SCIENCE > ATMOSPHERE") == "ATMOSPHERE"

    def test_extract_term_simple(self, generator):
        """Should return simple terms unchanged."""
        assert generator._extract_term("MODIS") == "MODIS"
        assert generator._extract_term("PRECIPITATION") == "PRECIPITATION"

    def test_enriches_platform_with_scheme(self, mock_base_generator):
        """Should use platform scheme for platform lookups."""
        platform_generator = KMSEnrichedEmbeddingGenerator(mock_base_generator, scheme="platforms")

        mock_term = KMSTerm(
            uuid="terra-uuid",
            scheme="platforms",
            term="TERRA",
            definition="Earth observation satellite",
        )
        with patch("util.embeddings.kms.lookup_term", return_value=mock_term) as mock_lookup:
            platform_generator.generate("TERRA", concept_type="collection", attribute="platforms")

            # Should have called lookup with platforms scheme
            mock_lookup.assert_called_with("TERRA", "platforms")

            call_args = mock_base_generator.generate.call_args
            enriched_text = call_args[0][0]
            assert "TERRA: Earth observation satellite" in enriched_text

    def test_enriches_instrument_with_scheme(self, mock_base_generator):
        """Should use instruments scheme for instrument lookups."""
        instrument_generator = KMSEnrichedEmbeddingGenerator(
            mock_base_generator, scheme="instruments"
        )

        mock_term = KMSTerm(
            uuid="modis-uuid",
            scheme="instruments",
            term="MODIS",
            definition="Moderate Resolution Imaging Spectroradiometer",
        )
        with patch("util.embeddings.kms.lookup_term", return_value=mock_term) as mock_lookup:
            instrument_generator.generate(
                "MODIS", concept_type="collection", attribute="instruments"
            )

            mock_lookup.assert_called_with("MODIS", "instruments")

            call_args = mock_base_generator.generate.call_args
            enriched_text = call_args[0][0]
            assert "MODIS: Moderate Resolution Imaging Spectroradiometer" in enriched_text


class TestRoutingEmbeddingGenerator:
    """Tests for RoutingEmbeddingGenerator."""

    def test_routes_to_specific_generator(self):
        """Should route to specific generator based on concept.attribute key."""
        default_gen = MagicMock(spec=BedrockEmbeddingGenerator)
        specific_gen = MagicMock(spec=BedrockEmbeddingGenerator)
        default_gen.model_id = "default"
        specific_gen.generate.return_value = [0.5] * 1024

        router = RoutingEmbeddingGenerator(
            generators={
                "collection.science_keywords": specific_gen,
                "default": default_gen,
            }
        )

        router.generate(
            "test text",
            concept_type="collection",
            attribute="science_keywords",
        )

        specific_gen.generate.assert_called_once()
        default_gen.generate.assert_not_called()

    def test_falls_back_to_default(self):
        """Should fall back to default for unmatched attributes."""
        default_gen = MagicMock(spec=BedrockEmbeddingGenerator)
        specific_gen = MagicMock(spec=BedrockEmbeddingGenerator)
        default_gen.model_id = "default"
        default_gen.generate.return_value = [0.1] * 1024

        router = RoutingEmbeddingGenerator(
            generators={
                "collection.science_keywords": specific_gen,
                "default": default_gen,
            }
        )

        router.generate(
            "test text",
            concept_type="collection",
            attribute="abstract",
        )

        default_gen.generate.assert_called_once()
        specific_gen.generate.assert_not_called()

    def test_falls_back_to_concept_type(self):
        """Should fall back to concept type if no attribute match."""
        default_gen = MagicMock(spec=BedrockEmbeddingGenerator)
        collection_gen = MagicMock(spec=BedrockEmbeddingGenerator)
        default_gen.model_id = "default"
        collection_gen.generate.return_value = [0.3] * 1024

        router = RoutingEmbeddingGenerator(
            generators={
                "collection": collection_gen,
                "default": default_gen,
            }
        )

        router.generate(
            "test text",
            concept_type="collection",
            attribute="title",
        )

        collection_gen.generate.assert_called_once()
        default_gen.generate.assert_not_called()

    def test_requires_default_generator(self):
        """Should raise ValueError if no default provided."""
        with pytest.raises(ValueError, match="Must provide either"):
            RoutingEmbeddingGenerator(generators={"collection": MagicMock()})


class TestGetEmbeddingGenerator:
    """Tests for the factory function."""

    def test_returns_routing_generator(self):
        """Factory should return a RoutingEmbeddingGenerator."""
        generator = get_embedding_generator()
        assert isinstance(generator, RoutingEmbeddingGenerator)

    def test_routes_science_keywords_to_kms_enriched(self):
        """Should route science_keywords to KMSEnrichedEmbeddingGenerator."""
        generator = get_embedding_generator()
        routed = generator._get_generator("collection", "science_keywords")
        assert isinstance(routed, KMSEnrichedEmbeddingGenerator)

    def test_routes_platforms_to_kms_enriched(self):
        """Should route platforms to KMSEnrichedEmbeddingGenerator."""
        generator = get_embedding_generator()
        routed = generator._get_generator("collection", "platforms")
        assert isinstance(routed, KMSEnrichedEmbeddingGenerator)

    def test_routes_instruments_to_kms_enriched(self):
        """Should route instruments to KMSEnrichedEmbeddingGenerator."""
        generator = get_embedding_generator()
        routed = generator._get_generator("collection", "instruments")
        assert isinstance(routed, KMSEnrichedEmbeddingGenerator)

    def test_routes_abstract_to_default(self):
        """Should route abstract to default BedrockEmbeddingGenerator."""
        generator = get_embedding_generator()
        routed = generator._get_generator("collection", "abstract")
        assert isinstance(routed, BedrockEmbeddingGenerator)
        assert not isinstance(routed, KMSEnrichedEmbeddingGenerator)

    def test_routes_variable_science_keywords_to_kms_enriched(self):
        """Should route variable science_keywords to KMSEnrichedEmbeddingGenerator."""
        generator = get_embedding_generator()
        routed = generator._get_generator("variable", "science_keywords")
        assert isinstance(routed, KMSEnrichedEmbeddingGenerator)


class TestBedrockEmbeddingGeneratorClient:
    """Tests for BedrockEmbeddingGenerator client behavior."""

    def test_uses_injected_client(self):
        """Should use injected client when provided."""
        import json

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"embedding": [0.1] * 10}).encode())
        }

        generator = BedrockEmbeddingGenerator(client=mock_client)
        generator.generate("test text")

        mock_client.invoke_model.assert_called_once()

    def test_uses_centralized_client_when_none_injected(self):
        """Should use get_bedrock_client() when no client is injected."""
        import json

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"embedding": [0.1] * 10}).encode())
        }

        with patch("util.embeddings.bedrock.get_bedrock_client", return_value=mock_client):
            generator = BedrockEmbeddingGenerator()
            generator.generate("test text")

            mock_client.invoke_model.assert_called_once()

    def test_client_property_returns_same_client(self):
        """Client property should return injected client consistently."""
        mock_client = MagicMock()
        generator = BedrockEmbeddingGenerator(client=mock_client)

        assert generator.client is mock_client
        assert generator.client is mock_client  # Same instance

    def test_generate_passes_text_to_bedrock(self):
        """Should pass text correctly to Bedrock invoke_model."""
        import json

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"embedding": [0.1] * 10}).encode())
        }

        generator = BedrockEmbeddingGenerator(client=mock_client)
        generator.generate("test input text")

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs["body"])
        assert body["inputText"] == "test input text"

    def test_generate_returns_embedding_vector(self):
        """Should return embedding vector from Bedrock response."""
        import json

        expected_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"embedding": expected_embedding}).encode())
        }

        generator = BedrockEmbeddingGenerator(client=mock_client)
        result = generator.generate("test text")

        assert result == expected_embedding

    def test_generate_raises_embedding_error_on_failure(self):
        """Should raise EmbeddingError when Bedrock call fails."""
        from util.embeddings.base import EmbeddingError

        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("Bedrock error")

        generator = BedrockEmbeddingGenerator(client=mock_client)

        with pytest.raises(EmbeddingError, match="Failed to generate embedding"):
            generator.generate("test text")
