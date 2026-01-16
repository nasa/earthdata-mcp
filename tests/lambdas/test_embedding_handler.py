"""Tests for the embedding lambda handler."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import responses


@pytest.fixture(autouse=True)
def set_env():
    """Set required environment variables."""
    os.environ["CMR_URL"] = "https://cmr.earthdata.nasa.gov"
    os.environ["DATABASE_SECRET_ID"] = "test-secret"
    os.environ["EMBEDDINGS_TABLE"] = "concept_embeddings"
    os.environ["EMBEDDING_MODEL"] = "amazon.titan-embed-text-v2:0"
    os.environ["BEDROCK_REGION"] = "us-east-1"
    yield


class TestExtractCollectionData:
    """Tests for extract_collection_data function."""

    def test_extracts_title(self):
        """Test that title is extracted as a chunk."""
        from lambdas.embedding.handler import extract_collection_data

        collection = {"EntryTitle": "Test Collection Title"}

        result = extract_collection_data("collection", "C1234-PROV", collection)

        assert len(result.chunks) == 1
        assert result.chunks[0].attribute == "title"
        assert result.chunks[0].text_content == "Test Collection Title"

    def test_extracts_abstract(self):
        """Test that abstract is extracted as a chunk."""
        from lambdas.embedding.handler import extract_collection_data

        collection = {"Abstract": "This is the abstract text."}

        result = extract_collection_data("collection", "C1234-PROV", collection)

        assert len(result.chunks) == 1
        assert result.chunks[0].attribute == "abstract"
        assert result.chunks[0].text_content == "This is the abstract text."

    def test_extracts_multiple_attributes(self):
        """Test that multiple attributes are extracted."""
        from lambdas.embedding.handler import extract_collection_data

        collection = {
            "EntryTitle": "Test Title",
            "Abstract": "Test Abstract",
            "Purpose": "Test Purpose",
        }

        result = extract_collection_data("collection", "C1234-PROV", collection)

        assert len(result.chunks) == 3
        attributes = {c.attribute for c in result.chunks}
        assert attributes == {"title", "abstract", "purpose"}

    def test_extracts_science_keywords_as_kms_terms(self):
        """Test that science keywords are extracted as KMS term references."""
        from lambdas.embedding.handler import extract_collection_data

        collection = {
            "ScienceKeywords": [
                {
                    "Category": "EARTH SCIENCE",
                    "Topic": "ATMOSPHERE",
                    "Term": "PRECIPITATION",
                }
            ]
        }

        result = extract_collection_data("collection", "C1234-PROV", collection)

        # Science keywords go to kms_terms, not chunks
        assert len(result.chunks) == 0
        assert len(result.kms_terms) == 1
        assert result.kms_terms[0].term == "PRECIPITATION"
        assert result.kms_terms[0].scheme == "sciencekeywords"

    def test_extracts_platforms_and_instruments_as_kms_terms(self):
        """Test that platforms and instruments are extracted as KMS term references."""
        from lambdas.embedding.handler import extract_collection_data

        collection = {
            "Platforms": [
                {
                    "ShortName": "TERRA",
                    "Instruments": [{"ShortName": "MODIS"}, {"ShortName": "ASTER"}],
                }
            ]
        }

        result = extract_collection_data("collection", "C1234-PROV", collection)

        # Platforms and instruments go to kms_terms
        assert len(result.chunks) == 0
        assert len(result.kms_terms) == 3

        terms = {(t.term, t.scheme) for t in result.kms_terms}
        assert ("TERRA", "platforms") in terms
        assert ("MODIS", "instruments") in terms
        assert ("ASTER", "instruments") in terms

    def test_empty_collection_returns_empty(self):
        """Test that empty collection returns empty result."""
        from lambdas.embedding.handler import extract_collection_data

        result = extract_collection_data("collection", "C1234-PROV", {})

        assert len(result.chunks) == 0
        assert len(result.kms_terms) == 0


class TestExtractVariableData:
    """Tests for extract_variable_data function."""

    def test_extracts_variable_attributes(self):
        """Test that variable attributes are extracted."""
        from lambdas.embedding.handler import extract_variable_data

        variable = {
            "Name": "sea_surface_temp",
            "LongName": "Sea Surface Temperature",
            "Definition": "Temperature of the sea surface",
        }

        result = extract_variable_data("variable", "V1234-PROV", variable)

        assert len(result.chunks) == 3
        attributes = {c.attribute for c in result.chunks}
        assert attributes == {"name", "long_name", "definition"}


class TestExtractCitationData:
    """Tests for extract_citation_data function."""

    def test_extracts_citation_attributes(self):
        """Test that citation attributes are extracted."""
        from lambdas.embedding.handler import extract_citation_data

        citation = {
            "Name": "Test Paper Title",
            "Abstract": "This paper describes important research findings.",
            "CitationMetadata": {
                "Publisher": "Test Publisher",
                "Author": [
                    {"Given": "Alice", "Family": "Author"},
                    {"Given": "Bob", "Family": "Writer"},
                ],
            },
        }

        result = extract_citation_data("citation", "CIT1234-PROV", citation)

        assert len(result.chunks) == 4
        attributes = {c.attribute for c in result.chunks}
        assert attributes == {"name", "authors", "publisher", "abstract"}

        # Check authors are formatted correctly
        authors_chunk = next(c for c in result.chunks if c.attribute == "authors")
        assert authors_chunk.text_content == "Alice Author; Bob Writer"


class TestExtractData:
    """Tests for extract_data routing function."""

    def test_dispatches_to_collection_extractor(self):
        """Test that collection type routes correctly."""
        from lambdas.embedding.handler import extract_data

        collection = {"EntryTitle": "Test"}
        result = extract_data("collection", "C1234-PROV", collection)

        assert len(result.chunks) == 1
        assert result.chunks[0].concept_type == "collection"

    def test_dispatches_to_variable_extractor(self):
        """Test that variable type routes correctly."""
        from lambdas.embedding.handler import extract_data

        variable = {"Name": "test_var"}
        result = extract_data("variable", "V1234-PROV", variable)

        assert len(result.chunks) == 1
        assert result.chunks[0].concept_type == "variable"

    def test_unknown_type_returns_empty(self):
        """Test that unknown type returns empty result."""
        from lambdas.embedding.handler import extract_data

        result = extract_data("unknown", "X1234-PROV", {})

        assert len(result.chunks) == 0
        assert len(result.kms_terms) == 0


class TestFetchConcept:
    """Tests for fetch_concept function."""

    @responses.activate
    def test_fetches_collection(self):
        """Test fetching a collection from CMR."""
        from util.cmr import fetch_concept

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/concepts/C1234-PROV/1.umm_json",
            json={"EntryTitle": "Test Collection"},
            status=200,
        )

        result = fetch_concept("C1234-PROV", "1")

        assert result["EntryTitle"] == "Test Collection"

    @responses.activate
    def test_raises_on_http_error(self):
        """Test that HTTP errors raise CMRError."""
        from util.cmr import CMRError, fetch_concept

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/concepts/C1234-PROV/1.umm_json",
            status=404,
        )

        with pytest.raises(CMRError):
            fetch_concept("C1234-PROV", "1")


class TestBedrockEmbeddingGenerator:
    """Tests for BedrockEmbeddingGenerator."""

    def test_generates_embedding(self):
        """Test that embeddings are generated via Bedrock."""
        from util.embeddings import BedrockEmbeddingGenerator

        mock_response = {
            "embedding": [0.1] * 1024,
            "inputTextTokenCount": 10,
        }
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }

        generator = BedrockEmbeddingGenerator(client=mock_client)
        embedding = generator.generate("test text")

        assert len(embedding) == 1024

    def test_passes_concept_type_and_attribute_to_trace(self):
        """Test that concept_type and attribute are passed to trace."""
        from util.embeddings import BedrockEmbeddingGenerator

        mock_response = {"embedding": [0.1] * 1024, "inputTextTokenCount": 10}
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }

        mock_trace = MagicMock()
        generator = BedrockEmbeddingGenerator(client=mock_client)
        generator.generate(
            "test text",
            concept_type="collection",
            attribute="abstract",
            trace=mock_trace,
        )

        # Trace generation should have been created with metadata
        mock_trace.generation.assert_called_once()


class TestPostgresDatastore:
    """Tests for PostgresEmbeddingDatastore."""

    def test_upsert_chunks(self):
        """Test upserting embedding chunks."""
        from util.datastores.postgres import PostgresEmbeddingDatastore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)

        with patch("util.datastores.postgres.get_db_connection", return_value=mock_conn):
            datastore = PostgresEmbeddingDatastore()
            chunks = [
                ("title", "Test Title", [0.1] * 1024),
                ("abstract", "Test Abstract", [0.2] * 1024),
            ]

            count = datastore.upsert_chunks("collection", "C1234-PROV", chunks)

            assert count == 2
            mock_conn.commit.assert_called_once()

    def test_upsert_associations(self):
        """Test upserting concept associations."""
        from util.datastores.postgres import PostgresEmbeddingDatastore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)

        with patch("util.datastores.postgres.get_db_connection", return_value=mock_conn):
            datastore = PostgresEmbeddingDatastore()
            associations = {"variables": ["V1234-PROV", "V5678-PROV"]}

            count = datastore.upsert_associations("collection", "C1234-PROV", associations)

            assert count == 2
            mock_conn.commit.assert_called_once()

    def test_empty_associations_returns_zero(self):
        """Test that empty associations returns 0."""
        from util.datastores.postgres import PostgresEmbeddingDatastore

        with patch("util.datastores.postgres.get_db_connection"):
            datastore = PostgresEmbeddingDatastore()
            count = datastore.upsert_associations("collection", "C1234-PROV", {})

            assert count == 0


class TestProcessConceptUpdate:
    """Tests for process_concept_update function."""

    def test_processes_collection_update(self):
        """Test processing a collection update message."""
        from lambdas.embedding.handler import process_concept_update

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.1] * 1024

        message = {
            "concept-type": "collection",
            "concept-id": "C1234-PROV",
            "revision-id": "1",
        }

        with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
            mock_fetch.return_value = {
                "EntryTitle": "Test Collection",
                "Abstract": "Test abstract",
            }
            with patch("lambdas.embedding.handler.fetch_associations") as mock_assoc:
                mock_assoc.return_value = {"variables": ["V1234-PROV"]}
                with patch("lambdas.embedding.handler.get_langfuse") as mock_langfuse:
                    mock_langfuse.return_value = None

                    process_concept_update(message, mock_repo, mock_embedder)

        # Should have upserted chunks
        mock_repo.upsert_chunks.assert_called_once()
        # Should have upserted associations
        mock_repo.upsert_associations.assert_called_once()

    def test_embedder_called_for_each_chunk(self):
        """Test that embedder.generate is called for each extracted chunk."""
        from lambdas.embedding.handler import process_concept_update

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.1] * 1024

        message = {
            "concept-type": "collection",
            "concept-id": "C1234-PROV",
            "revision-id": "1",
        }

        with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
            mock_fetch.return_value = {
                "EntryTitle": "MODIS Sea Surface Temperature",
                "Abstract": "Daily measurements of ocean temperature",
                "Purpose": "Climate monitoring",
            }
            with patch("lambdas.embedding.handler.fetch_associations") as mock_assoc:
                mock_assoc.return_value = {}
                with patch("lambdas.embedding.handler.get_langfuse") as mock_langfuse:
                    mock_langfuse.return_value = None

                    process_concept_update(message, mock_repo, mock_embedder)

        # Should have called generate 3 times (title, abstract, purpose)
        assert mock_embedder.generate.call_count == 3

        # Verify each call had the correct text
        call_texts = [call[0][0] for call in mock_embedder.generate.call_args_list]
        assert "MODIS Sea Surface Temperature" in call_texts
        assert "Daily measurements of ocean temperature" in call_texts
        assert "Climate monitoring" in call_texts

    def test_embedder_called_with_concept_type_and_attribute(self):
        """Test that embedder receives concept_type and attribute for routing."""
        from lambdas.embedding.handler import process_concept_update

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.1] * 1024

        message = {
            "concept-type": "collection",
            "concept-id": "C1234-PROV",
            "revision-id": "1",
        }

        with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
            mock_fetch.return_value = {"EntryTitle": "Test Title"}
            with patch("lambdas.embedding.handler.fetch_associations") as mock_assoc:
                mock_assoc.return_value = {}
                with patch("lambdas.embedding.handler.get_langfuse") as mock_langfuse:
                    mock_langfuse.return_value = None

                    process_concept_update(message, mock_repo, mock_embedder)

        # Verify embedder was called with concept_type and attribute
        call_kwargs = mock_embedder.generate.call_args
        assert call_kwargs.kwargs.get("concept_type") == "collection"
        assert call_kwargs.kwargs.get("attribute") == "title"


class TestProcessKMSTerms:
    """Tests for process_kms_terms function."""

    def test_looks_up_kms_terms(self):
        """Test that KMS lookup is called for extracted terms."""
        from lambdas.embedding.handler import KMSTermRef, process_kms_terms
        from util.kms import KMSTerm

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.1] * 1024

        kms_terms = [
            KMSTermRef(term="MODIS", scheme="instruments"),
            KMSTermRef(term="TERRA", scheme="platforms"),
        ]

        mock_kms_term = KMSTerm(
            uuid="test-uuid",
            scheme="instruments",
            term="MODIS",
            definition="Imaging Spectroradiometer",
        )

        with patch("lambdas.embedding.handler.lookup_term") as mock_lookup:
            mock_lookup.return_value = mock_kms_term

            process_kms_terms(kms_terms, mock_repo, mock_embedder)

        # Should have looked up both terms
        assert mock_lookup.call_count == 2
        mock_lookup.assert_any_call("MODIS", "instruments")
        mock_lookup.assert_any_call("TERRA", "platforms")

    def test_embeds_new_kms_terms(self):
        """Test that new KMS terms are embedded and stored."""
        from lambdas.embedding.handler import KMSTermRef, process_kms_terms
        from util.kms import KMSTerm

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None  # Not in database yet
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.5] * 1024

        kms_terms = [KMSTermRef(term="MODIS", scheme="instruments")]

        mock_kms_term = KMSTerm(
            uuid="modis-uuid",
            scheme="instruments",
            term="MODIS",
            definition="Moderate Resolution Imaging Spectroradiometer",
        )

        with patch("lambdas.embedding.handler.lookup_term") as mock_lookup:
            mock_lookup.return_value = mock_kms_term

            uuids = process_kms_terms(kms_terms, mock_repo, mock_embedder)

        # Should have generated embedding for the term + definition
        mock_embedder.generate.assert_called_once()
        call_text = mock_embedder.generate.call_args[0][0]
        assert "MODIS" in call_text
        assert "Moderate Resolution Imaging Spectroradiometer" in call_text

        # Should have stored the embedding
        mock_repo.upsert_kms_embedding.assert_called_once()

        # Should return the UUID
        assert uuids == ["modis-uuid"]

    def test_skips_existing_kms_embeddings(self):
        """Test that existing KMS embeddings are not re-generated."""
        from lambdas.embedding.handler import KMSTermRef, process_kms_terms
        from util.kms import KMSTerm

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = {"embedding": [0.1] * 1024}  # Already exists
        mock_embedder = MagicMock()

        kms_terms = [KMSTermRef(term="MODIS", scheme="instruments")]

        mock_kms_term = KMSTerm(
            uuid="modis-uuid",
            scheme="instruments",
            term="MODIS",
            definition="Imaging Spectroradiometer",
        )

        with patch("lambdas.embedding.handler.lookup_term") as mock_lookup:
            mock_lookup.return_value = mock_kms_term

            uuids = process_kms_terms(kms_terms, mock_repo, mock_embedder)

        # Should NOT have generated embedding (already exists)
        mock_embedder.generate.assert_not_called()
        mock_repo.upsert_kms_embedding.assert_not_called()

        # Should still return the UUID for association
        assert uuids == ["modis-uuid"]

    def test_deduplicates_kms_terms(self):
        """Test that duplicate terms are only processed once."""
        from lambdas.embedding.handler import KMSTermRef, process_kms_terms
        from util.kms import KMSTerm

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.1] * 1024

        # Same term twice
        kms_terms = [
            KMSTermRef(term="MODIS", scheme="instruments"),
            KMSTermRef(term="MODIS", scheme="instruments"),
        ]

        mock_kms_term = KMSTerm(
            uuid="modis-uuid",
            scheme="instruments",
            term="MODIS",
            definition="Definition",
        )

        with patch("lambdas.embedding.handler.lookup_term") as mock_lookup:
            mock_lookup.return_value = mock_kms_term

            process_kms_terms(kms_terms, mock_repo, mock_embedder)

        # Should only look up once
        assert mock_lookup.call_count == 1


class TestFullEmbeddingFlow:
    """Integration tests for the full embedding generation flow."""

    def test_collection_with_kms_terms_full_flow(self):
        """Test full flow: collection metadata -> extraction -> embedding -> storage."""
        from lambdas.embedding.handler import process_concept_update
        from util.kms import KMSTerm

        mock_repo = MagicMock()
        mock_repo.get_kms_embedding.return_value = None
        mock_embedder = MagicMock()
        mock_embedder.generate.return_value = [0.1] * 1024

        message = {
            "concept-type": "collection",
            "concept-id": "C1234-PROV",
            "revision-id": "1",
        }

        # Realistic collection metadata
        collection_metadata = {
            "EntryTitle": "MODIS/Terra Sea Surface Temperature",
            "Abstract": "Daily global sea surface temperature measurements",
            "ScienceKeywords": [
                {
                    "Category": "EARTH SCIENCE",
                    "Topic": "OCEANS",
                    "Term": "OCEAN TEMPERATURE",
                    "VariableLevel1": "SEA SURFACE TEMPERATURE",
                }
            ],
            "Platforms": [
                {
                    "ShortName": "TERRA",
                    "Instruments": [{"ShortName": "MODIS"}],
                }
            ],
        }

        mock_kms_terms = {
            ("SEA SURFACE TEMPERATURE", "sciencekeywords"): KMSTerm(
                uuid="sst-uuid",
                scheme="sciencekeywords",
                term="SEA SURFACE TEMPERATURE",
                definition="Ocean temp",
            ),
            ("TERRA", "platforms"): KMSTerm(
                uuid="terra-uuid",
                scheme="platforms",
                term="TERRA",
                definition="Satellite",
            ),
            ("MODIS", "instruments"): KMSTerm(
                uuid="modis-uuid",
                scheme="instruments",
                term="MODIS",
                definition="Imager",
            ),
        }

        def lookup_side_effect(term, scheme):
            return mock_kms_terms.get((term, scheme))

        with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
            mock_fetch.return_value = collection_metadata
            with patch("lambdas.embedding.handler.fetch_associations") as mock_assoc:
                mock_assoc.return_value = {}
                with patch("lambdas.embedding.handler.lookup_term") as mock_lookup:
                    mock_lookup.side_effect = lookup_side_effect
                    with patch("lambdas.embedding.handler.get_langfuse") as mock_langfuse:
                        mock_langfuse.return_value = None

                        process_concept_update(message, mock_repo, mock_embedder)

        # Verify concept chunks were embedded (title + abstract = 2)
        chunk_embed_calls = [
            c
            for c in mock_embedder.generate.call_args_list
            if c.kwargs.get("concept_type") == "collection"
        ]
        assert len(chunk_embed_calls) == 2

        # Verify KMS terms were looked up
        assert mock_lookup.call_count == 3  # SST, TERRA, MODIS

        # Verify KMS embeddings were generated (3 new terms)
        kms_embed_calls = [
            c
            for c in mock_embedder.generate.call_args_list
            if c.kwargs.get("concept_type") == "kms"
        ]
        assert len(kms_embed_calls) == 3

        # Verify concept chunks were stored
        mock_repo.upsert_chunks.assert_called_once()
        call_args = mock_repo.upsert_chunks.call_args
        assert call_args[0][0] == "collection"
        assert call_args[0][1] == "C1234-PROV"

        # Verify KMS associations were created
        mock_repo.upsert_concept_kms_associations.assert_called_once()
        assoc_call = mock_repo.upsert_concept_kms_associations.call_args
        assert set(assoc_call[0][2]) == {"sst-uuid", "terra-uuid", "modis-uuid"}


class TestProcessConceptDelete:
    """Tests for process_concept_delete function."""

    def test_deletes_embeddings_and_associations(self):
        """Test that delete removes chunks and associations."""
        from lambdas.embedding.handler import process_concept_delete

        mock_repo = MagicMock()
        mock_repo.delete_chunks.return_value = 3
        mock_repo.delete_associations.return_value = 2
        mock_repo.delete_concept_kms_associations.return_value = 5

        message = {"concept-id": "C1234-PROV"}

        process_concept_delete(message, mock_repo)

        mock_repo.delete_chunks.assert_called_once_with("C1234-PROV")
        mock_repo.delete_associations.assert_called_once_with("C1234-PROV")
        mock_repo.delete_concept_kms_associations.assert_called_once_with("C1234-PROV")


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_handler_processes_sqs_event(self):
        """Test that handler processes SQS messages."""
        from lambdas.embedding.handler import handler

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(
                        {
                            "action": "concept-update",
                            "concept-type": "collection",
                            "concept-id": "C1234-PROV",
                            "revision-id": "1",
                        }
                    ),
                }
            ]
        }

        with patch("lambdas.embedding.handler.get_datastore") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_kms_embedding.return_value = None
            mock_get_repo.return_value = mock_repo
            with patch("lambdas.embedding.handler.get_embedding_generator") as mock_get_gen:
                mock_embedder = MagicMock()
                mock_embedder.generate.return_value = [0.1] * 1024
                mock_get_gen.return_value = mock_embedder
                with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
                    mock_fetch.return_value = {"EntryTitle": "Test"}
                    with patch("lambdas.embedding.handler.fetch_associations") as mock_assoc:
                        mock_assoc.return_value = {}
                        with patch("lambdas.embedding.handler.get_langfuse") as mock_langfuse:
                            mock_langfuse.return_value = None
                            with patch("lambdas.embedding.handler.flush_langfuse"):
                                result = handler(event, None)

        assert result["batchItemFailures"] == []

    def test_handler_reports_failures(self):
        """Test that handler reports message failures."""
        from lambdas.embedding.handler import handler

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(
                        {
                            "action": "concept-update",
                            "concept-type": "collection",
                            "concept-id": "C1234-PROV",
                            "revision-id": "1",
                        }
                    ),
                }
            ]
        }

        with patch("lambdas.embedding.handler.get_datastore") as mock_get_repo:
            mock_repo = MagicMock()
            mock_get_repo.return_value = mock_repo
            with patch("lambdas.embedding.handler.get_embedding_generator") as mock_get_gen:
                mock_get_gen.return_value = MagicMock()
                with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
                    mock_fetch.side_effect = Exception("CMR error")
                    with patch("lambdas.embedding.handler.flush_langfuse"):
                        result = handler(event, None)

        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-1"

    def test_handler_continues_on_partial_failure(self):
        """Test that handler continues processing after a failure."""
        from lambdas.embedding.handler import handler

        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(
                        {
                            "action": "concept-update",
                            "concept-type": "collection",
                            "concept-id": "C1234-PROV",
                            "revision-id": "1",
                        }
                    ),
                },
                {
                    "messageId": "msg-2",
                    "body": json.dumps(
                        {
                            "action": "concept-update",
                            "concept-type": "collection",
                            "concept-id": "C5678-PROV",
                            "revision-id": "1",
                        }
                    ),
                },
            ]
        }

        call_count = [0]

        def fetch_side_effect(concept_id, revision_id):
            call_count[0] += 1
            if concept_id == "C1234-PROV":
                raise Exception("CMR error")
            return {"EntryTitle": "Test"}

        with patch("lambdas.embedding.handler.get_datastore") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_kms_embedding.return_value = None
            mock_get_repo.return_value = mock_repo
            with patch("lambdas.embedding.handler.get_embedding_generator") as mock_get_gen:
                mock_embedder = MagicMock()
                mock_embedder.generate.return_value = [0.1] * 1024
                mock_get_gen.return_value = mock_embedder
                with patch("lambdas.embedding.handler.fetch_concept") as mock_fetch:
                    mock_fetch.side_effect = fetch_side_effect
                    with patch("lambdas.embedding.handler.fetch_associations") as mock_assoc:
                        mock_assoc.return_value = {}
                        with patch("lambdas.embedding.handler.get_langfuse") as mock_langfuse:
                            mock_langfuse.return_value = None
                            with patch("lambdas.embedding.handler.flush_langfuse"):
                                result = handler(event, None)

        # Both messages should have been attempted
        assert call_count[0] == 2
        # Only the first should have failed
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-1"
