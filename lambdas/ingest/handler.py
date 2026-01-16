"""
Ingest Lambda - SNS receiver that forwards concept events to FIFO queue.

Receives concept update/delete events from CMR SNS topic and pushes them
to a FIFO SQS queue for ordered processing by the embedding lambda.
"""

import json
import logging
import os

from util.sqs import get_sqs_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMBEDDING_QUEUE_URL = os.environ.get("EMBEDDING_QUEUE_URL")

REQUIRED_FIELDS = {"concept-type", "concept-id", "action", "revision-id"}
VALID_ACTIONS = {"concept-update", "concept-delete"}


class InvalidMessageError(Exception):
    """Raised when an SNS message is malformed or missing required fields."""


def validate_message(message: dict) -> None:
    """
    Validate that the SNS message contains all required fields.

    Args:
        message: Parsed SNS message body.

    Raises:
        InvalidMessageError: If required fields are missing or action is invalid.
    """
    missing = REQUIRED_FIELDS - message.keys()
    if missing:
        raise InvalidMessageError(f"Missing required fields: {missing}")

    if message["action"] not in VALID_ACTIONS:
        raise InvalidMessageError(
            f"Invalid action '{message['action']}'. Must be one of: {VALID_ACTIONS}"
        )


def build_fifo_message(message: dict) -> dict:
    """
    Build the SQS FIFO message parameters.

    Args:
        message: Validated SNS message.

    Returns:
        Dict with MessageBody, MessageGroupId, and MessageDeduplicationId.
    """
    concept_type = message["concept-type"]
    concept_id = message["concept-id"]
    revision_id = message["revision-id"]

    return {
        "QueueUrl": EMBEDDING_QUEUE_URL,
        "MessageBody": json.dumps(message),
        "MessageGroupId": f"{concept_type}:{concept_id}",
        "MessageDeduplicationId": f"{concept_id}:{revision_id}",
    }


def process_record(record: dict) -> dict:
    """
    Process a single SNS record from the event.

    Args:
        record: SNS record from the Lambda event.

    Returns:
        Dict with concept_id and status.
    """
    sns_message = record.get("Sns", {})
    message_id = sns_message.get("MessageId", "unknown")

    try:
        message = json.loads(sns_message.get("Message", "{}"))
        validate_message(message)

        fifo_params = build_fifo_message(message)
        response = get_sqs_client().send_message(**fifo_params)

        logger.info(
            "Queued %s for %s:%s (revision %s) -> SQS MessageId: %s",
            message["action"],
            message["concept-type"],
            message["concept-id"],
            message["revision-id"],
            response["MessageId"],
        )

        return {
            "concept_id": message["concept-id"],
            "status": "queued",
            "sqs_message_id": response["MessageId"],
        }

    except json.JSONDecodeError as e:
        logger.error("Failed to parse SNS message %s: %s", message_id, e)
        raise InvalidMessageError(f"Invalid JSON in SNS message: {e}") from e

    except InvalidMessageError:
        logger.error("Invalid message %s: %s", message_id, sns_message.get("Message"))
        raise


def handler(event: dict, context) -> dict:
    """
    Lambda handler for processing CMR concept events from SNS.

    Args:
        event: Lambda event containing SNS records.
        context: Lambda context (unused).

    Returns:
        Dict with processing results.
    """
    records = event.get("Records", [])
    logger.info("Processing %d SNS record(s)", len(records))

    results = []
    errors = []

    for record in records:
        try:
            result = process_record(record)
            results.append(result)
        except (InvalidMessageError, Exception) as e:
            errors.append(
                {
                    "message_id": record.get("Sns", {}).get("MessageId", "unknown"),
                    "error": str(e),
                }
            )

    response = {
        "processed": len(results),
        "failed": len(errors),
        "results": results,
    }

    if errors:
        response["errors"] = errors
        logger.warning("Completed with %d error(s): %s", len(errors), errors)
    else:
        logger.info("Successfully processed %d record(s)", len(results))

    return response
