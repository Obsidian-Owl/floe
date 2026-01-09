"""Unit tests for PostgreSQL fixture.

Tests for testing.fixtures.postgres module including PostgresConfig
and connection info utilities. Integration tests are in test_postgres_integration.py.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from testing.fixtures.postgres import (
    PostgresConfig,
    PostgresConnectionError,
    create_connection,
    get_connection_info,
)


class TestPostgresConfig:
    """Tests for PostgresConfig model."""

    @pytest.mark.requirement("9c-FR-010")
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PostgresConfig()
        assert config.host == "postgres"
        assert config.port == 5432
        assert config.user == "floe"
        assert config.database == "floe_test"
        assert config.namespace == "floe-test"

    @pytest.mark.requirement("9c-FR-010")
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = PostgresConfig(
            host="custom-host",
            port=5433,
            user="custom_user",
            password=SecretStr("custom_pass"),
            database="custom_db",
        )
        assert config.host == "custom-host"
        assert config.port == 5433
        assert config.user == "custom_user"
        assert config.database == "custom_db"

    @pytest.mark.requirement("9c-FR-010")
    def test_k8s_host_property(self) -> None:
        """Test K8s DNS hostname generation."""
        config = PostgresConfig(host="postgres", namespace="test-ns")
        assert config.k8s_host == "postgres.test-ns.svc.cluster.local"

    @pytest.mark.requirement("9c-FR-010")
    def test_password_is_secret(self) -> None:
        """Test password is SecretStr type."""
        config = PostgresConfig(password=SecretStr("secret123"))
        assert isinstance(config.password, SecretStr)
        # SecretStr should mask in repr
        assert "secret123" not in repr(config)

    @pytest.mark.requirement("9c-FR-010")
    def test_port_validation(self) -> None:
        """Test port must be in valid range."""
        with pytest.raises(Exception):  # noqa: B017
            PostgresConfig(port=0)
        with pytest.raises(Exception):  # noqa: B017
            PostgresConfig(port=70000)

    @pytest.mark.requirement("9c-FR-010")
    def test_frozen_model(self) -> None:
        """Test PostgresConfig is immutable."""
        config = PostgresConfig()
        with pytest.raises(Exception):  # noqa: B017
            config.host = "other-host"

    @pytest.mark.requirement("9c-FR-010")
    def test_config_from_env(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "POSTGRES_HOST": "env-host",
                "POSTGRES_PORT": "5434",
                "POSTGRES_USER": "env_user",
                "POSTGRES_DATABASE": "env_db",
            },
        ):
            config = PostgresConfig()
            assert config.host == "env-host"
            assert config.port == 5434
            assert config.user == "env_user"
            assert config.database == "env_db"


class TestCreateConnection:
    """Tests for create_connection function."""

    @pytest.mark.requirement("9c-FR-010")
    def test_raises_on_missing_psycopg2(self) -> None:
        """Test raises helpful error when psycopg2 not installed."""
        config = PostgresConfig()

        with patch.dict("sys.modules", {"psycopg2": None}):
            with pytest.raises(PostgresConnectionError) as exc_info:
                create_connection(config)
            assert "psycopg2 not installed" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-010")
    def test_raises_on_connection_failure(self) -> None:
        """Test raises PostgresConnectionError on connection failure."""
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("Connection refused")
        mock_psycopg2.Error = Exception

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            config = PostgresConfig()
            with pytest.raises(PostgresConnectionError) as exc_info:
                create_connection(config)
            assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-010")
    def test_connection_uses_config_values(self) -> None:
        """Test connection is created with config values."""
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_psycopg2.Error = Exception

        with patch.dict("sys.modules", {"psycopg2": mock_psycopg2}):
            config = PostgresConfig(
                host="test-host",
                port=5432,
                user="test_user",
                password=SecretStr("test_pass"),
                database="test_db",
            )
            result = create_connection(config)

            mock_psycopg2.connect.assert_called_once_with(
                host="test-host",
                port=5432,
                user="test_user",
                password="test_pass",
                database="test_db",
            )
            assert result == mock_conn


class TestGetConnectionInfo:
    """Tests for get_connection_info function."""

    @pytest.mark.requirement("9c-FR-010")
    def test_returns_connection_info(self) -> None:
        """Test returns expected connection info."""
        config = PostgresConfig(
            host="test-host",
            port=5432,
            user="test_user",
            database="test_db",
            namespace="test-ns",
        )
        info = get_connection_info(config)

        assert info["host"] == "test-host"
        assert info["port"] == 5432
        assert info["user"] == "test_user"
        assert info["database"] == "test_db"
        assert info["namespace"] == "test-ns"
        assert info["k8s_host"] == "test-host.test-ns.svc.cluster.local"

    @pytest.mark.requirement("9c-FR-010")
    def test_does_not_expose_password(self) -> None:
        """Test password is not included in connection info."""
        config = PostgresConfig(password=SecretStr("secret123"))
        info = get_connection_info(config)

        assert "password" not in info
        assert "secret123" not in str(info)
