"""
Bootstrap Lambda - Bulk load concepts from CMR into the embedding pipeline.

Supports collections, variables, and citations. Accepts search parameters
as a dictionary from AWS Console for flexible querying.

Example invocation payload:
{
    "concept_type": "collection",
    "search_params": {
        "consortium": "EOSDIS",
        "has_granules": "true"
    },
    "page_size": 500,
    "dry_run": false
}
"""

import json
import logging
import os
from typing import Any

from util.cmr import CMRError, extract_concept_info, search_cmr
from util.sqs import get_sqs_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def send_to_queue(queue_url: str, messages: list[dict[str, Any]]) -> int:
    """
    Send messages to the FIFO queue in batches.

    Args:
        queue_url: The SQS queue URL
        messages: List of message dictionaries

    Returns:
        Number of messages successfully sent
    """
    sent = 0

    # SQS SendMessageBatch supports up to 10 messages
    for i in range(0, len(messages), 10):
        batch = messages[i : i + 10]
        entries = []

        for idx, msg in enumerate(batch):
            concept_id = msg["concept-id"]
            revision_id = msg["revision-id"]
            concept_type = msg["concept-type"]

            entries.append(
                {
                    "Id": str(idx),
                    "MessageBody": json.dumps(msg),
                    "MessageGroupId": f"{concept_type}:{concept_id}",
                    "MessageDeduplicationId": f"{concept_id}:{revision_id}",
                }
            )

        try:
            response = get_sqs_client().send_message_batch(
                QueueUrl=queue_url,
                Entries=entries,
            )
            sent += len(response.get("Successful", []))

            if failed := response.get("Failed", []):
                logger.warning("Failed to send %d messages: %s", len(failed), failed)

        except Exception as e:
            logger.error("Error sending batch to SQS: %s", e)
            raise

    return sent


def handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for bootstrap processing.

    Accepts event payload with:
        - concept_type: "collection", "variable", or "citation"
        - search_params: Dictionary of CMR search parameters
        - page_size: Optional, defaults to 500
        - dry_run: Optional, if true only logs what would be sent

    Returns:
        Summary of bootstrap operation
    """
    concept_type = event.get("concept_type", "collection")
    search_params = event.get("search_params", {})
    page_size = event.get("page_size", 500)
    dry_run = event.get("dry_run", False)
    queue_url = os.environ.get("EMBEDDING_QUEUE_URL")

    logger.info(
        "Starting bootstrap: concept_type=%s, search_params=%s, page_size=%d, dry_run=%s",
        concept_type,
        search_params,
        page_size,
        dry_run,
    )

    if not queue_url and not dry_run:
        raise ValueError("EMBEDDING_QUEUE_URL environment variable not set")

    total_processed = 0
    total_sent = 0
    total_errors = 0

    for items in search_cmr(concept_type, search_params, page_size):
        messages = []

        for item in items:
            try:
                msg = extract_concept_info(concept_type, item)
                messages.append(msg)
                total_processed += 1
            except CMRError as e:
                logger.warning("Error extracting concept info: %s", e)
                total_errors += 1

        if dry_run:
            logger.info("[DRY RUN] Would send %d messages to queue", len(messages))
            total_sent += len(messages)
        else:
            sent = send_to_queue(queue_url, messages)
            total_sent += sent
            logger.info("Sent %d messages to queue", sent)

    summary = {
        "concept_type": concept_type,
        "search_params": search_params,
        "total_processed": total_processed,
        "total_sent": total_sent,
        "total_errors": total_errors,
        "dry_run": dry_run,
    }

    logger.info("Bootstrap complete: %s", summary)
    return summary
