"""
AWS Secrets Manager Utility

This module provides functionality to retrieve secrets from AWS Secrets Manager.
"""

import json
import logging
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_secret(secret_name):
    """
    Retrieve a secret from AWS Secrets Manager.

    Args:
        secret_name (str): The name or ARN of the secret to retrieve.

    Returns:
        dict: The secret value as a dictionary.

    Raises:
        ClientError: If there's an error retrieving the secret.
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.error("Error retrieving secret: %s", e)
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response["SecretString"]
    return json.loads(secret)
