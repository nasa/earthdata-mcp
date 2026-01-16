"""Tests for the bootstrap lambda handler."""

import os

import pytest
import responses

from lambdas.bootstrap.handler import handler, send_to_queue
from util.cmr import CMRError, extract_concept_info, search_cmr


@pytest.fixture(autouse=True)
def set_env():
    """Set required environment variables."""
    os.environ["CMR_URL"] = "https://cmr.earthdata.nasa.gov"
    os.environ["EMBEDDING_QUEUE_URL"] = (
        "https://sqs.us-east-1.amazonaws.com/123456789/test-queue.fifo"
    )
    yield


class TestSearchCmr:
    """Tests for search_cmr function."""

    @responses.activate
    def test_search_cmr_returns_items(self):
        """Test that search_cmr yields items from CMR."""
        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={
                "hits": 2,
                "items": [
                    {"meta": {"concept-id": "C1234-PROV", "revision-id": 1}},
                    {"meta": {"concept-id": "C5678-PROV", "revision-id": 2}},
                ],
            },
            status=200,
        )

        results = list(search_cmr("collection", {}, page_size=100))

        assert len(results) == 1  # One page of results
        assert len(results[0]) == 2
        assert results[0][0]["meta"]["concept-id"] == "C1234-PROV"

    @responses.activate
    def test_search_cmr_paginates(self):
        """Test that search_cmr handles pagination."""
        # First page
        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={
                "hits": 3,
                "items": [
                    {"meta": {"concept-id": "C1-PROV", "revision-id": 1}},
                    {"meta": {"concept-id": "C2-PROV", "revision-id": 1}},
                ],
            },
            status=200,
        )
        # Second page
        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={
                "hits": 3,
                "items": [
                    {"meta": {"concept-id": "C3-PROV", "revision-id": 1}},
                ],
            },
            status=200,
        )

        results = list(search_cmr("collection", {}, page_size=2))

        assert len(results) == 2  # Two pages
        assert len(results[0]) == 2
        assert len(results[1]) == 1

    @responses.activate
    def test_search_cmr_stops_on_empty(self):
        """Test that search_cmr stops when no items returned."""
        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={"hits": 0, "items": []},
            status=200,
        )

        results = list(search_cmr("collection", {}, page_size=100))

        assert len(results) == 0

    def test_search_cmr_invalid_concept_type(self):
        """Test that search_cmr raises for invalid concept type."""
        with pytest.raises(CMRError, match="Unsupported concept_type"):
            list(search_cmr("invalid_type", {}))

    @responses.activate
    def test_search_cmr_passes_search_params(self):
        """Test that search_cmr passes search params to CMR."""
        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={"hits": 0, "items": []},
            status=200,
        )

        list(search_cmr("collection", {"consortium": "EOSDIS", "has_granules": "true"}))

        assert "consortium=EOSDIS" in responses.calls[0].request.url
        assert "has_granules=true" in responses.calls[0].request.url


class TestExtractConceptInfo:
    """Tests for extract_concept_info function."""

    def test_extracts_concept_info(self):
        """Test that concept info is correctly extracted."""
        item = {"meta": {"concept-id": "C1234-PROVIDER", "revision-id": 5}}

        result = extract_concept_info("collection", item)

        assert result["concept-type"] == "collection"
        assert result["concept-id"] == "C1234-PROVIDER"
        assert result["revision-id"] == 5
        assert result["action"] == "concept-update"

    def test_raises_on_missing_concept_id(self):
        """Test that missing concept-id raises CMRError."""
        item = {"meta": {"revision-id": 5}}

        with pytest.raises(CMRError, match="Missing concept-id"):
            extract_concept_info("collection", item)

    def test_raises_on_missing_revision_id(self):
        """Test that missing revision-id raises CMRError."""
        item = {"meta": {"concept-id": "C1234-PROVIDER"}}

        with pytest.raises(CMRError, match="Missing concept-id or revision-id"):
            extract_concept_info("collection", item)


class TestSendToQueue:
    """Tests for send_to_queue function."""

    def test_sends_messages_to_queue(self, mocker):
        """Test that messages are sent to the FIFO queue."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}, {"Id": "1"}],
            "Failed": [],
        }

        messages = [
            {
                "concept-type": "collection",
                "concept-id": "C1234-PROV",
                "revision-id": 1,
                "action": "concept-update",
            },
            {
                "concept-type": "collection",
                "concept-id": "C5678-PROV",
                "revision-id": 2,
                "action": "concept-update",
            },
        ]

        sent = send_to_queue("https://sqs.example.com/queue", messages)

        assert sent == 2
        mock_sqs.send_message_batch.assert_called_once()

    def test_batches_messages(self, mocker):
        """Test that messages are batched (max 10 per batch)."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        # First batch of 10, second batch of 5
        mock_sqs.send_message_batch.side_effect = [
            {"Successful": [{"Id": str(i)} for i in range(10)], "Failed": []},
            {"Successful": [{"Id": str(i)} for i in range(5)], "Failed": []},
        ]

        # Create 15 messages to test batching
        messages = [
            {
                "concept-type": "collection",
                "concept-id": f"C{i}-PROV",
                "revision-id": i,
                "action": "concept-update",
            }
            for i in range(15)
        ]

        sent = send_to_queue("https://sqs.example.com/queue", messages)

        assert sent == 15
        assert mock_sqs.send_message_batch.call_count == 2


class TestHandler:
    """Tests for the main handler function."""

    @responses.activate
    def test_handler_processes_collections(self, mocker):
        """Test handler processes collections and sends to queue."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}, {"Id": "1"}],
            "Failed": [],
        }

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={
                "hits": 2,
                "items": [
                    {"meta": {"concept-id": "C1234-PROV", "revision-id": 1}},
                    {"meta": {"concept-id": "C5678-PROV", "revision-id": 2}},
                ],
            },
            status=200,
        )

        event = {
            "concept_type": "collection",
            "search_params": {"consortium": "EOSDIS"},
            "page_size": 100,
        }

        result = handler(event, None)

        assert result["concept_type"] == "collection"
        assert result["total_processed"] == 2
        assert result["total_sent"] == 2
        assert result["total_errors"] == 0

    @responses.activate
    def test_handler_dry_run(self, mocker):
        """Test handler dry run mode doesn't send to queue."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={
                "hits": 2,
                "items": [
                    {"meta": {"concept-id": "C1234-PROV", "revision-id": 1}},
                    {"meta": {"concept-id": "C5678-PROV", "revision-id": 2}},
                ],
            },
            status=200,
        )

        event = {
            "concept_type": "collection",
            "search_params": {},
            "dry_run": True,
        }

        result = handler(event, None)

        assert result["dry_run"] is True
        assert result["total_processed"] == 2
        assert result["total_sent"] == 2  # Would have sent
        mock_sqs.send_message_batch.assert_not_called()

    @responses.activate
    def test_handler_default_values(self, mocker):
        """Test handler uses default values."""
        mocker.patch("util.sqs._client", mocker.MagicMock())

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/collections.umm_json",
            json={"hits": 0, "items": []},
            status=200,
        )

        # Minimal event - should use defaults
        event = {}

        result = handler(event, None)

        assert result["concept_type"] == "collection"  # default
        assert result["dry_run"] is False  # default

    @responses.activate
    def test_handler_processes_variables(self, mocker):
        """Test handler processes variables."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}],
            "Failed": [],
        }

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/variables.umm_json",
            json={
                "hits": 1,
                "items": [
                    {"meta": {"concept-id": "V1234-PROV", "revision-id": 1}},
                ],
            },
            status=200,
        )

        event = {"concept_type": "variable"}

        result = handler(event, None)

        assert result["concept_type"] == "variable"
        assert result["total_processed"] == 1

    @responses.activate
    def test_handler_processes_citations(self, mocker):
        """Test handler processes citations."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}],
            "Failed": [],
        }

        responses.add(
            responses.GET,
            "https://cmr.earthdata.nasa.gov/search/citations.umm_json",
            json={
                "hits": 1,
                "items": [
                    {"meta": {"concept-id": "CIT1234-PROV", "revision-id": 1}},
                ],
            },
            status=200,
        )

        event = {"concept_type": "citation"}

        result = handler(event, None)

        assert result["concept_type"] == "citation"
        assert result["total_processed"] == 1
