"""Tests for embedding module"""

import json
from unittest.mock import patch, Mock

import pytest

from util.embedding import EmbeddingGenerator, create_embedding_generator


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator class"""

    @patch("util.embedding.boto3.client")
    def test_init_with_aws_model_type(self, mock_boto_client):
        """Test initialization with AWS model type"""
        mock_bedrock = Mock()
        mock_boto_client.return_value = mock_bedrock

        generator = EmbeddingGenerator("amazon.titan-embed-text-v2:0", "aws")

        assert generator.model_name == "amazon.titan-embed-text-v2:0"
        assert generator.model_type == "aws"
        mock_boto_client.assert_called_once_with(service_name="bedrock-runtime")

    @patch("util.embedding.boto3.client")
    def test_init_with_invalid_model_type(
        self, mock_boto_client
    ):  # pylint: disable=unused-argument
        """Test initialization with invalid model type"""
        with pytest.raises(ValueError, match="Invalid model_type"):
            EmbeddingGenerator("some-model", "invalid")

    @patch("util.embedding.boto3.client")
    def test_generate_embedding_aws_success(self, mock_boto_client):
        """Test successful embedding generation with AWS"""
        mock_bedrock = Mock()
        mock_response_body = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}

        mock_response = {"body": Mock()}
        mock_response["body"].read.return_value = json.dumps(
            mock_response_body
        ).encode()

        mock_bedrock.invoke_model.return_value = mock_response
        mock_boto_client.return_value = mock_bedrock

        generator = EmbeddingGenerator("amazon.titan-embed-text-v2:0", "aws")
        result = generator.generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3, 0.4, 0.5]

        # Verify the call was made with correct parameters
        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "amazon.titan-embed-text-v2:0"
        assert call_kwargs["accept"] == "application/json"
        assert call_kwargs["contentType"] == "application/json"

        # Verify the body contains the input text
        body_dict = json.loads(call_kwargs["body"])
        assert body_dict["inputText"] == "test text"

    @patch("util.embedding.boto3.client")
    @patch("util.embedding.sys.exit")
    def test_generate_embedding_aws_failure(self, mock_exit, mock_boto_client):
        """Test embedding generation failure with AWS"""
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = Exception("AWS service error")
        mock_boto_client.return_value = mock_bedrock

        generator = EmbeddingGenerator("amazon.titan-embed-text-v2:0", "aws")
        generator.generate_embedding("test text")

        mock_exit.assert_called_once_with(1)

    @patch("util.embedding.boto3.client")
    def test_generate_embedding_unsupported_model_type(self, mock_boto_client):
        """Test generate_embedding with unsupported model type after init"""
        mock_boto_client.return_value = Mock()

        generator = EmbeddingGenerator("amazon.titan-embed-text-v2:0", "aws")
        # Manually change model_type to test error handling
        generator.model_type = "unsupported"

        with pytest.raises(ValueError, match="Invalid model_type"):
            generator.generate_embedding("test text")

    @patch("util.embedding.boto3.client")
    def test_model_type_case_insensitive(self, mock_boto_client):
        """Test that model_type is case insensitive"""
        mock_boto_client.return_value = Mock()

        generator = EmbeddingGenerator("amazon.titan-embed-text-v2:0", "AWS")
        assert generator.model_type == "aws"

        generator2 = EmbeddingGenerator("amazon.titan-embed-text-v2:0", "AwS")
        assert generator2.model_type == "aws"


class TestCreateEmbeddingGenerator:
    """Tests for create_embedding_generator function"""

    @patch("util.embedding.os.getenv")
    @patch("util.embedding.boto3.client")
    def test_create_with_default_titan_model(self, mock_boto_client, mock_getenv):
        """Test creating generator with default titan model"""
        mock_getenv.return_value = "titan"
        mock_boto_client.return_value = Mock()

        config = {
            "titan": {"model-name": "amazon.titan-embed-text-v2:0", "model-type": "aws"}
        }

        generator = create_embedding_generator(config)

        assert generator.model_name == "amazon.titan-embed-text-v2:0"
        assert generator.model_type == "aws"

    @patch("util.embedding.os.getenv")
    @patch("util.embedding.boto3.client")
    def test_create_with_custom_model(self, mock_boto_client, mock_getenv):
        """Test creating generator with custom model"""
        mock_getenv.return_value = "custom"
        mock_boto_client.return_value = Mock()

        config = {
            "custom": {
                "model-name": "amazon.titan-embed-text-v1:0",
                "model-type": "aws",
            }
        }

        generator = create_embedding_generator(config)

        assert generator.model_name == "amazon.titan-embed-text-v1:0"

    @patch("util.embedding.os.getenv")
    @patch("util.embedding.sys.exit")
    @patch("util.embedding.EmbeddingGenerator")
    def test_create_with_unsupported_model(
        self, mock_embedding_generator, mock_exit, mock_getenv
    ):
        """Test creating generator with unsupported model exits"""
        mock_getenv.return_value = "unsupported"
        # The mock generator will be returned if the exit isn't called
        mock_embedding_generator.return_value = "mock_generator"

        config = {
            "titan": {"model-name": "amazon.titan-embed-text-v2:0", "model-type": "aws"}
        }

        # Should exit and not return
        assert create_embedding_generator(config) is None
        mock_exit.assert_called_once_with(1)

    @patch("util.embedding.os.getenv")
    @patch("util.embedding.boto3.client")
    def test_create_with_none_config(self, mock_boto_client, mock_getenv):
        """Test creating generator with None config uses default"""
        mock_getenv.return_value = "titan"
        mock_boto_client.return_value = Mock()

        generator = create_embedding_generator(None)

        assert generator.model_name == "amazon.titan-embed-text-v2:0"
        assert generator.model_type == "aws"

    @patch("util.embedding.os.getenv")
    @patch("util.embedding.boto3.client")
    def test_create_with_multiple_models_in_config(self, mock_boto_client, mock_getenv):
        """Test creating generator with multiple models in config"""
        mock_getenv.return_value = "model2"
        mock_boto_client.return_value = Mock()

        config = {
            "model1": {"model-name": "amazon.model1", "model-type": "aws"},
            "model2": {"model-name": "amazon.model2", "model-type": "aws"},
            "model3": {"model-name": "amazon.model3", "model-type": "aws"},
        }

        generator = create_embedding_generator(config)

        assert generator.model_name == "amazon.model2"
