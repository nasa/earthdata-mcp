"""Tests for the ingest lambda handler."""

import json

import pytest

from lambdas.ingest.handler import (
    InvalidMessageError,
    handler,
    process_record,
)


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv(
        "EMBEDDING_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789/test-queue.fifo",
    )


class TestMessageValidation:
    """Tests for message validation through process_record."""

    def _make_sns_record(self, message: dict) -> dict:
        """Helper to wrap a message in SNS record format."""
        return {"Sns": {"MessageId": "test-msg", "Message": json.dumps(message)}}

    def test_valid_update_message_passes(self, mocker):
        """Test that valid update messages pass validation."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message.return_value = {"MessageId": "sqs-123"}

        record = self._make_sns_record(
            {
                "concept-type": "collection",
                "concept-id": "C1234-PROVIDER",
                "revision-id": 1,
                "action": "concept-update",
            }
        )

        # Should not raise
        result = process_record(record)
        assert result["status"] == "queued"

    def test_valid_delete_message_passes(self, mocker):
        """Test that valid delete messages pass validation."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message.return_value = {"MessageId": "sqs-123"}

        record = self._make_sns_record(
            {
                "concept-type": "collection",
                "concept-id": "C1234-PROVIDER",
                "revision-id": 1,
                "action": "concept-delete",
            }
        )

        # Should not raise
        result = process_record(record)
        assert result["status"] == "queued"

    def test_missing_concept_type_raises(self):
        """Test that missing concept-type raises InvalidMessageError."""
        record = self._make_sns_record(
            {
                "concept-id": "C1234-PROVIDER",
                "revision-id": 1,
                "action": "concept-update",
            }
        )

        with pytest.raises(InvalidMessageError, match="validation failed"):
            process_record(record)

    def test_missing_concept_id_raises(self):
        """Test that missing concept-id raises InvalidMessageError."""
        record = self._make_sns_record(
            {
                "concept-type": "collection",
                "revision-id": 1,
                "action": "concept-update",
            }
        )

        with pytest.raises(InvalidMessageError, match="validation failed"):
            process_record(record)

    def test_missing_revision_id_raises(self):
        """Test that missing revision-id raises InvalidMessageError."""
        record = self._make_sns_record(
            {
                "concept-type": "collection",
                "concept-id": "C1234-PROVIDER",
                "action": "concept-update",
            }
        )

        with pytest.raises(InvalidMessageError, match="validation failed"):
            process_record(record)

    def test_missing_action_raises(self):
        """Test that missing action raises InvalidMessageError."""
        record = self._make_sns_record(
            {
                "concept-type": "collection",
                "concept-id": "C1234-PROVIDER",
                "revision-id": 1,
            }
        )

        with pytest.raises(InvalidMessageError, match="validation failed"):
            process_record(record)

    def test_invalid_action_raises(self):
        """Test that invalid action raises InvalidMessageError."""
        record = self._make_sns_record(
            {
                "concept-type": "collection",
                "concept-id": "C1234-PROVIDER",
                "revision-id": 1,
                "action": "invalid-action",
            }
        )

        with pytest.raises(InvalidMessageError, match="validation failed"):
            process_record(record)


class TestHandler:
    """Tests for the main handler function."""

    def test_handler_processes_valid_sns_event(self, mocker):
        """Test handler processes valid SNS event and sends to SQS."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message.return_value = {"MessageId": "sqs-msg-123"}

        sns_message = {
            "concept-type": "collection",
            "concept-id": "C1234-PROVIDER",
            "revision-id": 1,
            "action": "concept-update",
        }

        event = {
            "Records": [
                {
                    "Sns": {
                        "MessageId": "test-msg-1",
                        "Message": json.dumps(sns_message),
                    }
                }
            ]
        }

        result = handler(event, None)

        assert result["processed"] == 1
        assert result["failed"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["concept_id"] == "C1234-PROVIDER"
        assert result["results"][0]["status"] == "queued"
        mock_sqs.send_message.assert_called_once()

    def test_handler_processes_multiple_records(self, mocker):
        """Test handler processes multiple SNS records."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message.return_value = {"MessageId": "sqs-msg-123"}

        event = {
            "Records": [
                {
                    "Sns": {
                        "MessageId": "test-msg-1",
                        "Message": json.dumps(
                            {
                                "concept-type": "collection",
                                "concept-id": "C1234-PROVIDER",
                                "revision-id": 1,
                                "action": "concept-update",
                            }
                        ),
                    }
                },
                {
                    "Sns": {
                        "MessageId": "test-msg-2",
                        "Message": json.dumps(
                            {
                                "concept-type": "variable",
                                "concept-id": "V5678-PROVIDER",
                                "revision-id": 2,
                                "action": "concept-update",
                            }
                        ),
                    }
                },
            ]
        }

        result = handler(event, None)

        assert result["processed"] == 2
        assert result["failed"] == 0
        assert mock_sqs.send_message.call_count == 2

    def test_handler_handles_invalid_message(self, mocker):
        """Test handler handles invalid messages gracefully."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)

        event = {
            "Records": [
                {
                    "Sns": {
                        "MessageId": "test-msg-1",
                        "Message": json.dumps({"invalid": "message"}),
                    }
                }
            ]
        }

        result = handler(event, None)

        assert result["processed"] == 0
        assert result["failed"] == 1
        assert "errors" in result
        mock_sqs.send_message.assert_not_called()

    def test_handler_handles_malformed_json(self, mocker):
        """Test handler handles malformed JSON gracefully."""
        mocker.patch("util.sqs._client", mocker.MagicMock())

        event = {
            "Records": [
                {
                    "Sns": {
                        "MessageId": "test-msg-1",
                        "Message": "not valid json",
                    }
                }
            ]
        }

        result = handler(event, None)

        assert result["processed"] == 0
        assert result["failed"] == 1
        assert "errors" in result

    def test_handler_partial_failure(self, mocker):
        """Test handler continues processing after individual failures."""
        mock_sqs = mocker.MagicMock()
        mocker.patch("util.sqs._client", mock_sqs)
        mock_sqs.send_message.return_value = {"MessageId": "sqs-msg-123"}

        event = {
            "Records": [
                {
                    "Sns": {
                        "MessageId": "test-msg-1",
                        "Message": json.dumps(
                            {
                                "concept-type": "collection",
                                "concept-id": "C1234-PROVIDER",
                                "revision-id": 1,
                                "action": "concept-update",
                            }
                        ),
                    }
                },
                {
                    "Sns": {
                        "MessageId": "test-msg-2",
                        "Message": json.dumps({"invalid": "message"}),
                    }
                },
                {
                    "Sns": {
                        "MessageId": "test-msg-3",
                        "Message": json.dumps(
                            {
                                "concept-type": "variable",
                                "concept-id": "V5678-PROVIDER",
                                "revision-id": 1,
                                "action": "concept-delete",
                            }
                        ),
                    }
                },
            ]
        }

        result = handler(event, None)

        assert result["processed"] == 2
        assert result["failed"] == 1
