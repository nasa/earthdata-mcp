"""Tests for util.environment."""

import pytest

from util.environment import get_client_id, get_environment


class TestGetEnvironment:
    """Tests for get_environment()."""

    def test_returns_environment_name_when_set(self, monkeypatch):
        """Should return the value of ENVIRONMENT_NAME."""
        monkeypatch.setenv("ENVIRONMENT_NAME", "uat")

        assert get_environment() == "uat"

    def test_returns_prod(self, monkeypatch):
        """Should return prod for a production deployment."""
        monkeypatch.setenv("ENVIRONMENT_NAME", "prod")

        assert get_environment() == "prod"

    def test_returns_test_for_ci(self, monkeypatch):
        """Should return test when set by CI/CD pipeline."""
        monkeypatch.setenv("ENVIRONMENT_NAME", "test")

        assert get_environment() == "test"

    def test_defaults_to_development_when_unset(self, monkeypatch):
        """Should default to 'development' when ENVIRONMENT_NAME is not set."""
        monkeypatch.delenv("ENVIRONMENT_NAME", raising=False)

        assert get_environment() == "development"


class TestGetClientId:
    """Tests for get_client_id()."""

    def test_builds_client_id_from_environment(self, monkeypatch):
        """Should combine environment into the EED client ID format."""
        monkeypatch.setenv("ENVIRONMENT_NAME", "uat")

        assert get_client_id() == "eed-uat-mcp"

    def test_returns_prod_client_id(self, monkeypatch):
        """Should return the correct production client ID."""
        monkeypatch.setenv("ENVIRONMENT_NAME", "prod")

        assert get_client_id() == "eed-prod-mcp"

    def test_defaults_to_development_when_environment_unset(self, monkeypatch):
        """Should use 'development' environment when ENVIRONMENT_NAME is not set."""
        monkeypatch.delenv("ENVIRONMENT_NAME", raising=False)

        assert get_client_id() == "eed-development-mcp"
