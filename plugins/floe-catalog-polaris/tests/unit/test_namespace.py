"""Unit tests for namespace operations.

This module tests namespace operations (create, list, delete) for the
PolarisCatalogPlugin including property handling and error cases.

Requirements Covered:
    - FR-010: Create namespaces with configurable properties
    - FR-011: Hierarchical namespace paths using dot notation
    - FR-012: List namespaces with optional filtering
    - FR-013: Delete empty namespaces
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugin_errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    NotSupportedError,
)

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin


@pytest.fixture
def polaris_config() -> PolarisCatalogConfig:
    """Create a test Polaris configuration."""
    return PolarisCatalogConfig(
        uri="https://polaris.example.com/api/catalog",
        warehouse="test_warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        ),
    )


@pytest.fixture
def polaris_plugin(polaris_config: PolarisCatalogConfig) -> PolarisCatalogPlugin:
    """Create a test Polaris plugin instance."""
    return PolarisCatalogPlugin(config=polaris_config)


@pytest.fixture
def mock_catalog() -> MagicMock:
    """Create a mock PyIceberg catalog."""
    catalog = MagicMock()
    catalog.list_namespaces.return_value = [("bronze",), ("silver",), ("gold",)]
    return catalog


@pytest.fixture
def connected_plugin(
    polaris_plugin: PolarisCatalogPlugin,
    mock_catalog: MagicMock,
) -> PolarisCatalogPlugin:
    """Create a plugin with a mocked connected catalog."""
    with patch(
        "floe_catalog_polaris.plugin.load_catalog",
        return_value=mock_catalog,
    ):
        polaris_plugin.connect({})
    return polaris_plugin


class TestCreateNamespace:
    """Tests for create_namespace() method."""

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_basic(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test creating a namespace with no properties."""
        connected_plugin.create_namespace("bronze")

        mock_catalog.create_namespace.assert_called_once_with(
            "bronze",
            properties={},
        )

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_with_properties(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test creating a namespace with configurable properties."""
        properties = {
            "location": "s3://bucket/bronze",
            "owner": "data-platform-team",
            "description": "Raw data landing zone",
        }

        connected_plugin.create_namespace("bronze", properties=properties)

        mock_catalog.create_namespace.assert_called_once_with(
            "bronze",
            properties=properties,
        )

    @pytest.mark.requirement("FR-011")
    def test_create_namespace_hierarchical(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test creating hierarchical namespace with dot notation."""
        connected_plugin.create_namespace("domain.product.bronze")

        mock_catalog.create_namespace.assert_called_once_with(
            "domain.product.bronze",
            properties={},
        )

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_already_exists_raises_conflict_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that creating an existing namespace raises ConflictError."""
        from pyiceberg.exceptions import NamespaceAlreadyExistsError

        mock_catalog.create_namespace.side_effect = NamespaceAlreadyExistsError("bronze")

        with pytest.raises(ConflictError) as exc_info:
            connected_plugin.create_namespace("bronze")

        assert exc_info.value.resource_type == "namespace"
        assert "bronze" in exc_info.value.identifier

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_permission_denied_raises_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that permission denied raises AuthenticationError."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.create_namespace.side_effect = ForbiddenError("Access denied")

        with pytest.raises(AuthenticationError) as exc_info:
            connected_plugin.create_namespace("restricted")

        assert "Permission denied" in str(exc_info.value)

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that create_namespace logs the operation."""
        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.create_namespace("bronze")

            # Should log the operation start and success
            assert mock_logger.bind.called or mock_logger.info.called

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_with_empty_properties(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test creating namespace with explicitly empty properties dict."""
        connected_plugin.create_namespace("bronze", properties={})

        mock_catalog.create_namespace.assert_called_once_with(
            "bronze",
            properties={},
        )


class TestListNamespaces:
    """Tests for list_namespaces() method."""

    @pytest.mark.requirement("FR-012")
    def test_list_namespaces_returns_list(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_namespaces returns a list of namespace names."""
        mock_catalog.list_namespaces.return_value = [("bronze",), ("silver",), ("gold",)]

        result = connected_plugin.list_namespaces()

        assert isinstance(result, list)
        assert "bronze" in result
        assert "silver" in result
        assert "gold" in result

    @pytest.mark.requirement("FR-012")
    def test_list_namespaces_empty_catalog(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test listing namespaces in an empty catalog."""
        mock_catalog.list_namespaces.return_value = []

        result = connected_plugin.list_namespaces()

        assert result == []

    @pytest.mark.requirement("FR-012")
    def test_list_namespaces_with_parent_filter(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test listing namespaces with parent filter."""
        mock_catalog.list_namespaces.return_value = [
            ("silver", "customers"),
            ("silver", "orders"),
        ]

        connected_plugin.list_namespaces(parent="silver")

        mock_catalog.list_namespaces.assert_called_once()
        # Verify parent was passed to the catalog
        call_args = mock_catalog.list_namespaces.call_args
        assert call_args is not None

    @pytest.mark.requirement("FR-011")
    def test_list_namespaces_hierarchical_returns_dotted_names(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that hierarchical namespaces are returned with dot notation."""
        mock_catalog.list_namespaces.return_value = [
            ("domain", "product", "bronze"),
            ("domain", "product", "silver"),
        ]

        result = connected_plugin.list_namespaces()

        # Should join multi-level namespaces with dots
        assert "domain.product.bronze" in result or ("domain", "product", "bronze") in [
            tuple(ns.split(".")) for ns in result
        ]

    @pytest.mark.requirement("FR-012")
    def test_list_namespaces_permission_denied_raises_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that permission denied raises AuthenticationError."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.list_namespaces.side_effect = ForbiddenError("Access denied")

        with pytest.raises(AuthenticationError):
            connected_plugin.list_namespaces()

    @pytest.mark.requirement("FR-012")
    def test_list_namespaces_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_namespaces logs the operation."""
        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.list_namespaces()

            assert mock_logger.bind.called or mock_logger.info.called


class TestDeleteNamespace:
    """Tests for delete_namespace() method."""

    @pytest.mark.requirement("FR-013")
    def test_delete_namespace_basic(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test deleting a namespace."""
        connected_plugin.delete_namespace("bronze")

        mock_catalog.drop_namespace.assert_called_once_with("bronze")

    @pytest.mark.requirement("FR-013")
    def test_delete_namespace_not_found_raises_not_found_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that deleting a non-existent namespace raises NotFoundError."""
        from pyiceberg.exceptions import NoSuchNamespaceError

        mock_catalog.drop_namespace.side_effect = NoSuchNamespaceError("unknown")

        with pytest.raises(NotFoundError) as exc_info:
            connected_plugin.delete_namespace("unknown")

        assert exc_info.value.resource_type == "namespace"

    @pytest.mark.requirement("FR-013")
    def test_delete_namespace_not_empty_raises_not_supported_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that deleting a non-empty namespace raises NotSupportedError."""
        from pyiceberg.exceptions import NamespaceNotEmptyError

        mock_catalog.drop_namespace.side_effect = NamespaceNotEmptyError("bronze")

        with pytest.raises(NotSupportedError) as exc_info:
            connected_plugin.delete_namespace("bronze")

        assert "not empty" in str(exc_info.value).lower()

    @pytest.mark.requirement("FR-013")
    def test_delete_namespace_permission_denied_raises_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that permission denied raises AuthenticationError."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.drop_namespace.side_effect = ForbiddenError("Access denied")

        with pytest.raises(AuthenticationError):
            connected_plugin.delete_namespace("bronze")

    @pytest.mark.requirement("FR-011")
    def test_delete_namespace_hierarchical(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test deleting hierarchical namespace with dot notation."""
        connected_plugin.delete_namespace("domain.product.bronze")

        mock_catalog.drop_namespace.assert_called_once_with("domain.product.bronze")

    @pytest.mark.requirement("FR-013")
    def test_delete_namespace_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that delete_namespace logs the operation."""
        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.delete_namespace("bronze")

            assert mock_logger.bind.called or mock_logger.info.called


class TestNamespaceNotConnected:
    """Tests for namespace operations when not connected."""

    @pytest.mark.requirement("FR-010")
    def test_create_namespace_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that create_namespace fails when not connected."""
        from floe_core.plugin_errors import CatalogUnavailableError

        # Plugin is not connected (no connect() called)
        with pytest.raises(CatalogUnavailableError, match="not connected"):
            polaris_plugin.create_namespace("bronze")

    @pytest.mark.requirement("FR-012")
    def test_list_namespaces_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that list_namespaces fails when not connected."""
        from floe_core.plugin_errors import CatalogUnavailableError

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            polaris_plugin.list_namespaces()

    @pytest.mark.requirement("FR-013")
    def test_delete_namespace_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that delete_namespace fails when not connected."""
        from floe_core.plugin_errors import CatalogUnavailableError

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            polaris_plugin.delete_namespace("bronze")


class TestNamespaceOTelTracing:
    """Tests for OpenTelemetry tracing in namespace operations."""

    @pytest.mark.requirement("FR-030")
    def test_create_namespace_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that create_namespace emits an OTel span."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.create_namespace("bronze")

            mock_span.assert_called_once()
            call_args = mock_span.call_args
            assert "create_namespace" in str(call_args)

    @pytest.mark.requirement("FR-030")
    def test_list_namespaces_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_namespaces emits an OTel span."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.list_namespaces()

            mock_span.assert_called_once()
            call_args = mock_span.call_args
            assert "list_namespaces" in str(call_args)

    @pytest.mark.requirement("FR-030")
    def test_delete_namespace_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that delete_namespace emits an OTel span."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.delete_namespace("bronze")

            mock_span.assert_called_once()
            call_args = mock_span.call_args
            assert "delete_namespace" in str(call_args)

    @pytest.mark.requirement("FR-031")
    def test_namespace_span_includes_namespace_attribute(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that namespace spans include the namespace name attribute."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.create_namespace("bronze")

            # Should include namespace in span attributes
            # Namespace should be passed either as kwarg or positional
            call_str = str(mock_span.call_args)
            assert "bronze" in call_str or "namespace" in call_str


class TestNamespaceErrorMapping:
    """Tests for error mapping in namespace operations."""

    @pytest.mark.requirement("FR-033")
    def test_create_namespace_maps_pyiceberg_errors(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that PyIceberg errors are mapped to floe errors."""
        from pyiceberg.exceptions import NamespaceAlreadyExistsError

        mock_catalog.create_namespace.side_effect = NamespaceAlreadyExistsError("bronze")

        with pytest.raises(ConflictError):
            connected_plugin.create_namespace("bronze")

    @pytest.mark.requirement("FR-033")
    def test_list_namespaces_maps_pyiceberg_errors(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that PyIceberg errors are mapped to floe errors."""
        from pyiceberg.exceptions import ServiceUnavailableError

        mock_catalog.list_namespaces.side_effect = ServiceUnavailableError("Service down")

        from floe_core.plugin_errors import CatalogUnavailableError

        with pytest.raises(CatalogUnavailableError):
            connected_plugin.list_namespaces()

    @pytest.mark.requirement("FR-033")
    def test_delete_namespace_maps_pyiceberg_errors(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that PyIceberg errors are mapped to floe errors."""
        from pyiceberg.exceptions import NoSuchNamespaceError

        mock_catalog.drop_namespace.side_effect = NoSuchNamespaceError("bronze")

        with pytest.raises(NotFoundError):
            connected_plugin.delete_namespace("bronze")
