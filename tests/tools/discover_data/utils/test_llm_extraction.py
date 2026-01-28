"""Tests for llm_extraction shared utilities."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from tools.discover_data.utils import llm_extraction


class TestLoadExtractionPrompt:
    """Test the load_extraction_prompt utility function."""

    def test_successful_prompt_load(self):
        """Load and prepare prompt with date replacement."""
        mock_prompt_content = "Today is {current_date}. Extract spatial info."
        mock_file = mock_open(read_data=mock_prompt_content)

        with patch("builtins.open", mock_file):
            result = llm_extraction.load_extraction_prompt("spatial_extraction.md", "2024-01-15")

            assert result == "Today is 2024-01-15. Extract spatial info."
            # Verify correct path was opened
            call_args = mock_file.call_args
            assert call_args[1]["encoding"] == "utf-8"
            # Verify the path includes prompts directory
            opened_path = str(call_args[0][0])
            assert "prompts" in opened_path
            assert "spatial_extraction.md" in opened_path

    def test_multiple_date_replacements(self):
        """Handle multiple {current_date} placeholders in prompt."""
        mock_prompt_content = "From: {current_date}\nTo: {current_date}\nProcess queries."
        mock_file = mock_open(read_data=mock_prompt_content)

        with patch("builtins.open", mock_file):
            result = llm_extraction.load_extraction_prompt("temporal_extraction.md", "2024-12-31")

            assert result == "From: 2024-12-31\nTo: 2024-12-31\nProcess queries."

    def test_prompt_without_date_placeholder(self):
        """Handle prompts that don't have {current_date} placeholder."""
        mock_prompt_content = "Extract location information from the query."
        mock_file = mock_open(read_data=mock_prompt_content)

        with (
            patch("builtins.open", mock_file),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = llm_extraction.load_extraction_prompt("test_prompt.md", "2024-01-01")

            # Should return unchanged prompt
            assert result == "Extract location information from the query."

    def test_prompt_file_not_found(self):
        """Raise FileNotFoundError if prompt file doesn't exist."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match="Required prompt file not found"),
        ):
            llm_extraction.load_extraction_prompt("nonexistent.md", "2024-01-01")

    def test_prompt_path_construction(self):
        """Verify prompt path is constructed correctly relative to module."""
        mock_file = mock_open(read_data="test content")

        with (
            patch("builtins.open", mock_file) as mock_open_call,
            patch("pathlib.Path.exists", return_value=True),
        ):
            llm_extraction.load_extraction_prompt("test.md", "2024-01-01")

            # Verify the constructed path
            opened_path = mock_open_call.call_args[0][0]
            assert isinstance(opened_path, Path)
            assert opened_path.name == "test.md"
            assert opened_path.parent.name == "prompts"

    def test_empty_prompt_file(self):
        """Handle empty prompt files gracefully."""
        mock_file = mock_open(read_data="")

        with (
            patch("builtins.open", mock_file),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = llm_extraction.load_extraction_prompt("empty.md", "2024-01-01")

            assert result == ""

    def test_prompt_with_special_characters(self):
        """Handle prompts with special characters and unicode."""
        mock_prompt_content = (
            "Current date: {current_date}\nExtract locations like: Paris, 北京, São Paulo"
        )
        mock_file = mock_open(read_data=mock_prompt_content)

        with (
            patch("builtins.open", mock_file),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = llm_extraction.load_extraction_prompt("unicode_prompt.md", "2024-06-15")

            assert (
                result == "Current date: 2024-06-15\nExtract locations like: Paris, 北京, São Paulo"
            )

    def test_date_format_preserved(self):
        """Date string is used exactly as provided without validation."""
        mock_prompt_content = "Date: {current_date}"
        mock_file = mock_open(read_data=mock_prompt_content)

        with (
            patch("builtins.open", mock_file),
            patch("pathlib.Path.exists", return_value=True),
        ):
            # Even with unusual date format, it should be inserted as-is
            result = llm_extraction.load_extraction_prompt("test.md", "January 27, 2026")

            assert result == "Date: January 27, 2026"


class TestConstants:
    """Test module-level constants."""

    def test_provider_constant(self):
        """PROVIDER constant should be 'bedrock'."""
        assert llm_extraction.PROVIDER == "bedrock"

    def test_model_id_constant(self):
        """MODEL_ID constant should be the nova-pro model."""
        assert llm_extraction.MODEL_ID == "amazon.nova-pro-v1:0"
        assert "nova-pro" in llm_extraction.MODEL_ID
        assert llm_extraction.MODEL_ID.startswith("amazon.")
