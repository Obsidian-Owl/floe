"""Unit tests for Dagster fixture.

Tests for testing.fixtures.dagster module including DagsterConfig
and instance utilities. Integration tests require Kind cluster.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from testing.fixtures.dagster import (
    DagsterConfig,
    DagsterConnectionError,
    check_webserver_health,
    create_dagster_instance,
    get_connection_info,
)


class TestDagsterConfig:
    """Tests for DagsterConfig model."""

    @pytest.mark.requirement("9c-FR-014")
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = DagsterConfig()
        assert config.host == "dagster-webserver"
        assert config.port == 3000
        assert config.use_ephemeral is True
        assert config.namespace == "floe-test"

    @pytest.mark.requirement("9c-FR-014")
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = DagsterConfig(
            host="custom-dagster",
            port=3001,
            storage_root="/tmp/dagster",
            use_ephemeral=False,
        )
        assert config.host == "custom-dagster"
        assert config.port == 3001
        assert config.storage_root == "/tmp/dagster"
        assert config.use_ephemeral is False

    @pytest.mark.requirement("9c-FR-014")
    def test_k8s_host_property(self) -> None:
        """Test K8s DNS hostname generation."""
        config = DagsterConfig(host="dagster-webserver", namespace="test-ns")
        assert config.k8s_host == "dagster-webserver.test-ns.svc.cluster.local"

    @pytest.mark.requirement("9c-FR-014")
    def test_graphql_url_property(self) -> None:
        """Test GraphQL URL generation."""
        config = DagsterConfig(host="dagster", port=3000)
        assert config.graphql_url == "http://dagster:3000/graphql"

    @pytest.mark.requirement("9c-FR-014")
    def test_port_validation(self) -> None:
        """Test port must be in valid range."""
        with pytest.raises(Exception):
            DagsterConfig(port=0)
        with pytest.raises(Exception):
            DagsterConfig(port=70000)

    @pytest.mark.requirement("9c-FR-014")
    def test_frozen_model(self) -> None:
        """Test DagsterConfig is immutable."""
        config = DagsterConfig()
        with pytest.raises(Exception):
            config.host = "other-host"  # type: ignore[misc]

    @pytest.mark.requirement("9c-FR-014")
    def test_config_from_env(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DAGSTER_HOST": "env-dagster",
                "DAGSTER_PORT": "3001",
            },
        ):
            config = DagsterConfig()
            assert config.host == "env-dagster"
            assert config.port == 3001


class TestCreateDagsterInstance:
    """Tests for create_dagster_instance function."""

    @pytest.mark.requirement("9c-FR-014")
    def test_raises_on_missing_dagster(self) -> None:
        """Test raises helpful error when dagster not installed."""
        config = DagsterConfig()

        with patch.dict("sys.modules", {"dagster": None}):
            with pytest.raises(DagsterConnectionError) as exc_info:
                create_dagster_instance(config)
            assert "dagster not installed" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-014")
    def test_ephemeral_instance_created(self) -> None:
        """Test ephemeral instance is created for ephemeral config."""
        mock_dagster = MagicMock()
        mock_instance = MagicMock()
        mock_dagster.DagsterInstance.ephemeral.return_value = mock_instance

        with patch.dict("sys.modules", {"dagster": mock_dagster}):
            config = DagsterConfig(use_ephemeral=True)
            result = create_dagster_instance(config)

            mock_dagster.DagsterInstance.ephemeral.assert_called_once()
            assert result == mock_instance

    @pytest.mark.requirement("9c-FR-014")
    def test_default_instance_for_non_ephemeral(self) -> None:
        """Test default instance is used for non-ephemeral config."""
        mock_dagster = MagicMock()
        mock_instance = MagicMock()
        mock_dagster.DagsterInstance.get.return_value = mock_instance

        with patch.dict("sys.modules", {"dagster": mock_dagster}):
            config = DagsterConfig(use_ephemeral=False)
            result = create_dagster_instance(config)

            mock_dagster.DagsterInstance.get.assert_called_once()
            assert result == mock_instance


class TestCheckWebserverHealth:
    """Tests for check_webserver_health function."""

    @pytest.mark.requirement("9c-FR-014")
    def test_returns_true_on_success(self) -> None:
        """Test returns True when webserver responds."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            config = DagsterConfig()
            result = check_webserver_health(config)
            assert result is True

    @pytest.mark.requirement("9c-FR-014")
    def test_returns_false_on_error(self) -> None:
        """Test returns False when webserver fails."""
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            config = DagsterConfig()
            result = check_webserver_health(config)
            assert result is False

    @pytest.mark.requirement("9c-FR-014")
    def test_returns_false_on_timeout(self) -> None:
        """Test returns False on timeout."""
        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            config = DagsterConfig()
            result = check_webserver_health(config)
            assert result is False


class TestGetConnectionInfo:
    """Tests for get_connection_info function."""

    @pytest.mark.requirement("9c-FR-014")
    def test_returns_connection_info(self) -> None:
        """Test returns expected connection info."""
        config = DagsterConfig(
            host="test-dagster",
            port=3000,
            use_ephemeral=True,
            namespace="test-ns",
        )
        info = get_connection_info(config)

        assert info["host"] == "test-dagster"
        assert info["port"] == 3000
        assert info["use_ephemeral"] is True
        assert info["namespace"] == "test-ns"
        assert "k8s_host" in info
        assert "graphql_url" in info

    @pytest.mark.requirement("9c-FR-014")
    def test_includes_graphql_url(self) -> None:
        """Test connection info includes GraphQL URL."""
        config = DagsterConfig(host="dagster", port=3000)
        info = get_connection_info(config)

        assert info["graphql_url"] == "http://dagster:3000/graphql"
