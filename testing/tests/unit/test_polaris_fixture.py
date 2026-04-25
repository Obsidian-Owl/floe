"""Unit tests for Polaris catalog fixture.

Tests for testing.fixtures.polaris module including PolarisConfig
and catalog utilities. Integration tests require Kind cluster.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from testing.fixtures.credentials import (
    get_minio_credentials,
    get_polaris_scope,
    get_polaris_warehouse,
)
from testing.fixtures.polaris import (
    PolarisConfig,
    PolarisConnectionError,
    create_polaris_catalog,
    get_connection_info,
    rewrite_table_io_for_host_access,
)
from testing.fixtures.services import ServiceEndpoint


class TestPolarisConfig:
    """Tests for PolarisConfig model."""

    @pytest.mark.requirement("9c-FR-012")
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PolarisConfig()
        assert config.uri == f"{ServiceEndpoint('polaris').url}/api/catalog"
        assert config.warehouse == get_polaris_warehouse()
        assert config.scope == get_polaris_scope()
        assert config.namespace == "floe-test"

    @pytest.mark.requirement("9c-FR-012")
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = PolarisConfig(
            uri="http://custom:8182/api/catalog",
            warehouse="custom_warehouse",
            credential=SecretStr("client:secret"),
            scope="CUSTOM_SCOPE",
        )
        assert config.uri == "http://custom:8182/api/catalog"
        assert config.warehouse == "custom_warehouse"
        assert config.scope == "CUSTOM_SCOPE"

    @pytest.mark.requirement("9c-FR-012")
    def test_k8s_uri_property(self) -> None:
        """Test K8s DNS URI generation."""
        config = PolarisConfig(
            uri="http://polaris:8181/api/catalog",
            namespace="test-ns",
        )
        expected = "http://polaris.test-ns.svc.cluster.local:8181/api/catalog"
        assert config.k8s_uri == expected

    @pytest.mark.requirement("9c-FR-012")
    def test_k8s_uri_preserves_path(self) -> None:
        """Test K8s URI preserves path component."""
        config = PolarisConfig(
            uri="http://polaris:8181/api/catalog/v1",
            namespace="test-ns",
        )
        assert "/api/catalog/v1" in config.k8s_uri

    @pytest.mark.requirement("RAC-7")
    def test_api_base_url_strips_catalog_suffix(self) -> None:
        """Test api_base_url derives the Polaris service root from catalog URI."""
        config = PolarisConfig(uri="http://polaris:8181/api/catalog")
        assert config.api_base_url == "http://polaris:8181"

    @pytest.mark.requirement("RAC-7")
    def test_api_base_url_preserves_path_prefix(self) -> None:
        """Test api_base_url keeps any path prefix before /api/catalog."""
        config = PolarisConfig(uri="http://gateway.example/prefix/api/catalog")
        assert config.api_base_url == "http://gateway.example/prefix"

    @pytest.mark.requirement("9c-FR-012")
    def test_credential_is_secret(self) -> None:
        """Test credential is SecretStr type."""
        config = PolarisConfig(credential=SecretStr("client:secret123"))
        assert isinstance(config.credential, SecretStr)
        assert "secret123" not in repr(config)

    @pytest.mark.requirement("9c-FR-012")
    def test_frozen_model(self) -> None:
        """Test PolarisConfig is immutable."""
        config = PolarisConfig()
        with pytest.raises(ValidationError):
            config.uri = "http://other:8181"

    @pytest.mark.requirement("9c-FR-012")
    def test_config_from_env(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "POLARIS_URI": "http://env-polaris:8181/api/catalog",
                "POLARIS_WAREHOUSE": "env_warehouse",
                "POLARIS_CREDENTIAL": "env_client:env_secret",
                "POLARIS_SCOPE": "ENV_SCOPE",
            },
        ):
            config = PolarisConfig()
            assert config.uri == "http://env-polaris:8181/api/catalog"
            assert config.warehouse == "env_warehouse"
            assert config.scope == "ENV_SCOPE"

    @pytest.mark.requirement("9c-FR-012")
    def test_config_uses_polaris_url_env_when_uri_missing(self) -> None:
        """Test POLARIS_URL expands to the catalog API path."""
        with patch.dict(os.environ, {"POLARIS_URL": "http://env-base:30181"}, clear=True):
            config = PolarisConfig()
            assert config.uri == "http://env-base:30181/api/catalog"

    @pytest.mark.requirement("9c-FR-012")
    def test_default_credential_uses_centralized_helper(self) -> None:
        """Test credential fallback comes from the shared credentials helper."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "testing.fixtures.polaris.get_polaris_credentials",
                return_value=("shared-id", "shared-secret"),
            ),
        ):
            config = PolarisConfig()
            assert config.credential.get_secret_value() == "shared-id:shared-secret"


class TestCreatePolarisCatalog:
    """Tests for create_polaris_catalog function."""

    @pytest.mark.requirement("9c-FR-012")
    def test_raises_on_missing_pyiceberg(self) -> None:
        """Test raises helpful error when pyiceberg not installed."""
        config = PolarisConfig()

        with patch.dict("sys.modules", {"pyiceberg.catalog": None}):
            with pytest.raises(PolarisConnectionError) as exc_info:
                create_polaris_catalog(config)
            assert "pyiceberg not installed" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-012")
    def test_catalog_created_with_config(self) -> None:
        """Test catalog is created with config values."""
        mock_pyiceberg = MagicMock()
        mock_catalog = MagicMock()
        mock_pyiceberg.load_catalog.return_value = mock_catalog

        with patch.dict("sys.modules", {"pyiceberg.catalog": mock_pyiceberg}):
            config = PolarisConfig(
                uri="http://test:8181/api/catalog",
                warehouse="test_warehouse",
                credential=SecretStr("test_client:test_secret"),
                scope="TEST_SCOPE",
            )
            result = create_polaris_catalog(config)
            expected_access, expected_secret = get_minio_credentials()

            mock_pyiceberg.load_catalog.assert_called_once_with(
                "polaris",
                type="rest",
                uri="http://test:8181/api/catalog",
                warehouse="test_warehouse",
                credential="test_client:test_secret",
                scope="TEST_SCOPE",
                **{
                    "s3.endpoint": ServiceEndpoint("minio").url,
                    "s3.access-key-id": expected_access,
                    "s3.secret-access-key": expected_secret,
                    "s3.region": "us-east-1",
                    "s3.path-style-access": "true",
                },
            )
            assert result == mock_catalog


class TestRewriteTableIoForHostAccess:
    """Tests for rewrite_table_io_for_host_access."""

    @pytest.mark.requirement("RAC-9")
    def test_rewrites_s3_endpoint_using_shared_minio_url(self) -> None:
        """Test the helper swaps the FileIO endpoint for host-side access."""
        replacement_io = object()
        pyiceberg_io = MagicMock()
        pyiceberg_io.load_file_io.return_value = replacement_io
        table = MagicMock()
        table.io = MagicMock(properties={"s3.endpoint": "http://cluster-minio:9000", "foo": "bar"})

        with (
            patch.dict("sys.modules", {"pyiceberg.io": pyiceberg_io}),
            patch.dict(os.environ, {"MINIO_URL": "http://host.minio:9000"}, clear=False),
        ):
            rewrite_table_io_for_host_access(table)

        pyiceberg_io.load_file_io.assert_called_once_with(
            properties={"s3.endpoint": "http://host.minio:9000", "foo": "bar"}
        )
        assert table.io is replacement_io


class TestGetConnectionInfo:
    """Tests for get_connection_info function."""

    @pytest.mark.requirement("9c-FR-012")
    def test_returns_connection_info(self) -> None:
        """Test returns expected connection info."""
        config = PolarisConfig(
            uri="http://test:8181/api/catalog",
            warehouse="test_warehouse",
            scope="TEST_SCOPE",
            namespace="test-ns",
        )
        info = get_connection_info(config)

        assert info["uri"] == "http://test:8181/api/catalog"
        assert info["warehouse"] == "test_warehouse"
        assert info["scope"] == "TEST_SCOPE"
        assert info["namespace"] == "test-ns"

    @pytest.mark.requirement("9c-FR-012")
    def test_does_not_expose_credential(self) -> None:
        """Test credential is not included in connection info."""
        config = PolarisConfig(credential=SecretStr("client:secret123"))
        info = get_connection_info(config)

        assert "credential" not in info
        assert "secret123" not in str(info)
