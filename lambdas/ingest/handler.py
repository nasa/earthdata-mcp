"""
Ingest Lambda - SNS receiver that forwards concept events to FIFO queue.

Receives concept update/delete events from CMR SNS topic and pushes them
to a FIFO SQS queue for ordered processing by the embedding lambda.
"""

import json
import logging
import os

from pydantic import ValidationError

from util.models import ConceptMessage
from util.sqs import get_sqs_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InvalidMessageError(Exception):
    """Raised when an SNS message is malformed or missing required fields."""


def process_record(record: dict) -> dict:
    """
    Process a single SNS record from the event.

    Parses and validates the message, then forwards it to the FIFO queue.
    """
    sns_message = record.get("Sns", {})
    message_id = sns_message.get("MessageId", "unknown")

    try:
        raw_message = json.loads(sns_message.get("Message", "{}"))
    except json.JSONDecodeError as e:
        logger.error("Failed to parse SNS message %s: %s", message_id, e)
        raise InvalidMessageError(f"Invalid JSON in SNS message: {e}") from e

    try:
        message = ConceptMessage.model_validate(raw_message)
    except ValidationError as e:
        logger.error("Invalid message %s: %s", message_id, e)
        raise InvalidMessageError(f"Message validation failed: {e}") from e

    queue_url = os.environ.get("EMBEDDING_QUEUE_URL")
    if not queue_url:
        raise ValueError("EMBEDDING_QUEUE_URL environment variable not set")

    response = get_sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=message.model_dump_json(by_alias=True),
        MessageGroupId=f"{message.concept_type}:{message.concept_id}",
        MessageDeduplicationId=f"{message.concept_id}:{message.revision_id}",
    )

    logger.info(
        "Queued %s for %s:%s (revision %s) -> SQS MessageId: %s",
        message.action,
        message.concept_type,
        message.concept_id,
        message.revision_id,
        response["MessageId"],
    )

    return {
        "concept_id": message.concept_id,
        "status": "queued",
        "sqs_message_id": response["MessageId"],
    }


def handler(event: dict, _context) -> dict:
    """
    Lambda handler for processing CMR concept events from SNS.

    Returns dict with processing results including count of processed/failed.
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
