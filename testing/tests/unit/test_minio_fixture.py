"""Unit tests for MinIO/S3 fixture.

Tests for testing.fixtures.minio module including MinIOConfig
and client utilities. Integration tests require Kind cluster.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from testing.fixtures.minio import (
    MinIOConfig,
    MinIOConnectionError,
    create_minio_client,
    get_connection_info,
)


class TestMinIOConfig:
    """Tests for MinIOConfig model."""

    @pytest.mark.requirement("9c-FR-013")
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = MinIOConfig()
        assert config.endpoint == "minio:9000"
        assert config.access_key == "minioadmin"
        assert config.secure is False
        assert config.region == "us-east-1"
        assert config.namespace == "floe-test"

    @pytest.mark.requirement("9c-FR-013")
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = MinIOConfig(
            endpoint="custom-minio:9001",
            access_key="custom_key",
            secret_key=SecretStr("custom_secret"),
            secure=True,
            region="eu-west-1",
        )
        assert config.endpoint == "custom-minio:9001"
        assert config.access_key == "custom_key"
        assert config.secure is True
        assert config.region == "eu-west-1"

    @pytest.mark.requirement("9c-FR-013")
    def test_k8s_endpoint_property(self) -> None:
        """Test K8s DNS endpoint generation."""
        config = MinIOConfig(endpoint="minio:9000", namespace="test-ns")
        assert config.k8s_endpoint == "minio.test-ns.svc.cluster.local:9000"

    @pytest.mark.requirement("9c-FR-013")
    def test_k8s_endpoint_without_port(self) -> None:
        """Test K8s endpoint when no port specified."""
        config = MinIOConfig(endpoint="minio", namespace="test-ns")
        assert config.k8s_endpoint == "minio.test-ns.svc.cluster.local:9000"

    @pytest.mark.requirement("9c-FR-013")
    def test_secret_key_is_secret(self) -> None:
        """Test secret key is SecretStr type."""
        config = MinIOConfig(secret_key=SecretStr("secret123"))
        assert isinstance(config.secret_key, SecretStr)
        assert "secret123" not in repr(config)

    @pytest.mark.requirement("9c-FR-013")
    def test_frozen_model(self) -> None:
        """Test MinIOConfig is immutable."""
        config = MinIOConfig()
        with pytest.raises(Exception):  # noqa: B017
            config.endpoint = "other:9000"

    @pytest.mark.requirement("9c-FR-013")
    def test_config_from_env(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "env-minio:9001",
                "AWS_ACCESS_KEY_ID": "env_key",
                "AWS_SECRET_ACCESS_KEY": "env_secret",
                "AWS_REGION": "ap-southeast-1",
            },
        ):
            config = MinIOConfig()
            assert config.endpoint == "env-minio:9001"
            assert config.access_key == "env_key"
            assert config.region == "ap-southeast-1"


class TestCreateMinioClient:
    """Tests for create_minio_client function."""

    @pytest.mark.requirement("9c-FR-013")
    def test_raises_on_missing_minio(self) -> None:
        """Test raises helpful error when minio not installed."""
        config = MinIOConfig()

        with patch.dict("sys.modules", {"minio": None}):
            with pytest.raises(MinIOConnectionError) as exc_info:
                create_minio_client(config)
            assert "minio not installed" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-013")
    def test_client_created_with_config(self) -> None:
        """Test client is created with config values."""
        mock_minio = MagicMock()
        mock_client = MagicMock()
        mock_minio.Minio.return_value = mock_client

        with patch.dict("sys.modules", {"minio": mock_minio}):
            config = MinIOConfig(
                endpoint="test:9000",
                access_key="test_key",
                secret_key=SecretStr("test_secret"),
                secure=True,
                region="us-west-2",
            )
            result = create_minio_client(config)

            mock_minio.Minio.assert_called_once_with(
                endpoint="test:9000",
                access_key="test_key",
                secret_key="test_secret",
                secure=True,
                region="us-west-2",
            )
            assert result == mock_client


class TestGetConnectionInfo:
    """Tests for get_connection_info function."""

    @pytest.mark.requirement("9c-FR-013")
    def test_returns_connection_info(self) -> None:
        """Test returns expected connection info."""
        config = MinIOConfig(
            endpoint="test:9000",
            access_key="test_key",
            secure=False,
            region="us-east-1",
            namespace="test-ns",
        )
        info = get_connection_info(config)

        assert info["endpoint"] == "test:9000"
        assert info["access_key"] == "test_key"
        assert info["secure"] is False
        assert info["region"] == "us-east-1"
        assert info["namespace"] == "test-ns"

    @pytest.mark.requirement("9c-FR-013")
    def test_does_not_expose_secret_key(self) -> None:
        """Test secret key is not included in connection info."""
        config = MinIOConfig(secret_key=SecretStr("secret123"))
        info = get_connection_info(config)

        assert "secret_key" not in info
        assert "secret123" not in str(info)
