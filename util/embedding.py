"""
Embedding Generation Module

This module provides functionality to generate text embeddings using AWS Bedrock services.
"""

import json
import sys
import os
import logging
import boto3


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    A class for generating text embeddings using AWS Bedrock services.

    This class provides methods to create vector representations (embeddings)
    of text using specified AWS Bedrock models. It handles the AWS
    authentication and API interactions necessary for embedding generation.

    Attributes:
        model_name (str): The name of the AWS Bedrock model to use for embeddings.
        model_type (str, optional): The type of model to use. Defaults to 'aws'.

    Note:
        Ensure that AWS credentials are properly set up in the environment
        before using this class.
    """

    def __init__(self, model_name, model_type="aws"):
        self.model_name = model_name
        self.model_type = model_type.lower()

        if self.model_type == "aws":
            self.bedrock = boto3.client(service_name="bedrock-runtime")
        else:
            raise ValueError(
                f"Invalid model_type: {self.model_type}. " "Supported type is 'aws'."
            )

    def generate_embedding(self, text):
        """
        Generate an embedding for the given text using the specified model type.

        This method delegates to the appropriate embedding generation method
        based on the model type specified during initialization.

        Parameters:
        text (str): The input text to generate an embedding for.

        Returns:
        array: The generated embedding vector.
        """
        if self.model_type == "aws":
            return self._generate_aws_embedding(text)

        raise ValueError(
            f"Invalid model_type: {self.model_type}. " "Supported type is 'aws'."
        )

    def _generate_aws_embedding(self, text):
        """
        Generate an embedding for the given text using AWS Bedrock service.

        This method sends the input text to AWS Bedrock and retrieves the corresponding
        vector embedding.

        Args:
            text (str): The input text to generate an embedding for.

        Returns:
            list: A vector representation (embedding) of the input text.
        """
        try:
            body = json.dumps({"inputText": text})
            response = self.bedrock.invoke_model(
                body=body,
                modelId=self.model_name,
                accept="application/json",
                contentType="application/json",
            )
            response_body = json.loads(response.get("body").read())
            return response_body["embedding"]
        except Exception as e:
            logger.error("An error occurred while generating embedding: %s", e)
            sys.exit(1)


def create_embedding_generator(supported_models_config: dict = None):
    """
    Create an embedding generator based on supported models.

    This function reads configuration for supported embedding models and creates
    an appropriate embedding generator.

    Args:
        supported_models_config (dict, optional): Dictionary containing supported models config.
            If None, will use default Titan model.

    Returns:
        EmbeddingGenerator: An instance of the EmbeddingGenerator class
        configured with the supported models. Returns None if model is not supported.
    """
    if supported_models_config is None:
        # Default configuration
        supported_models_config = {
            "titan": {"model-name": "amazon.titan-embed-text-v2:0", "model-type": "aws"}
        }

    embd_gen = os.getenv("EMBD_GEN", "titan")

    if embd_gen in supported_models_config:
        embedding_generator = EmbeddingGenerator(
            supported_models_config[embd_gen]["model-name"],
            supported_models_config[embd_gen]["model-type"],
        )
        logger.info(
            "Initialized EmbeddingGenerator with model: %s",
            embedding_generator.model_name,
        )
        return embedding_generator

    supported_models_string = ", ".join(supported_models_config.keys())
    logger.error("EMBD_GEN must be one of: %s", supported_models_string)
    sys.exit(1)
