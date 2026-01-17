"""Unit tests for IcebergTableManager.

Tests the IcebergTableManager class using mock CatalogPlugin and StoragePlugin
fixtures. These tests validate initialization, configuration, and core operations.

Note: Tests are written TDD-style before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


# =============================================================================
# Manager Initialization Tests (T012)
# =============================================================================


class TestIcebergTableManagerInit:
    """Tests for IcebergTableManager.__init__ method."""

    @pytest.mark.requirement("FR-008")
    def test_init_with_required_plugins(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager initializes with required plugins."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        assert manager is not None
        assert manager._catalog_plugin is mock_catalog_plugin
        assert manager._storage_plugin is mock_storage_plugin

    @pytest.mark.requirement("FR-008")
    def test_init_with_optional_config(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager initializes with optional config."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig

        config = IcebergTableManagerConfig(
            max_commit_retries=5,
            default_retention_days=30,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        assert manager._config == config
        assert manager._config.max_commit_retries == 5
        assert manager._config.default_retention_days == 30

    @pytest.mark.requirement("FR-008")
    def test_init_uses_default_config(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager uses default config when not provided."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import CommitStrategy

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Default config values
        assert manager._config.max_commit_retries == 3
        assert manager._config.default_commit_strategy == CommitStrategy.FAST_APPEND

    @pytest.mark.requirement("FR-009")
    def test_init_connects_to_catalog(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager connects to catalog during init."""
        from floe_iceberg import IcebergTableManager

        # Verify connect not called yet
        assert mock_catalog_plugin.connect_config is None

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Verify connect was called
        assert mock_catalog_plugin._connected is True
        assert manager._catalog is not None

    @pytest.mark.requirement("FR-010")
    def test_init_retrieves_fileio(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager retrieves FileIO from storage plugin."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Verify FileIO was retrieved
        assert manager._fileio is not None
        assert manager._fileio is mock_storage_plugin._fileio

    @pytest.mark.requirement("FR-011")
    def test_init_creates_logger(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager creates structured logger."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Verify logger exists and is bound with context
        assert manager._log is not None

    @pytest.mark.requirement("FR-008")
    def test_init_requires_catalog_plugin(
        self,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager raises error without catalog plugin."""
        from floe_iceberg import IcebergTableManager

        with pytest.raises(TypeError):
            IcebergTableManager(
                storage_plugin=mock_storage_plugin,  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-008")
    def test_init_requires_storage_plugin(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test IcebergTableManager raises error without storage plugin."""
        from floe_iceberg import IcebergTableManager

        with pytest.raises(TypeError):
            IcebergTableManager(
                catalog_plugin=mock_catalog_plugin,  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-008")
    def test_init_validates_catalog_plugin_type(
        self,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager validates catalog plugin type."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import ValidationError

        with pytest.raises((TypeError, ValidationError)):
            IcebergTableManager(
                catalog_plugin="not a plugin",  # type: ignore[arg-type]
                storage_plugin=mock_storage_plugin,
            )

    @pytest.mark.requirement("FR-008")
    def test_init_validates_storage_plugin_type(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test IcebergTableManager validates storage plugin type."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import ValidationError

        with pytest.raises((TypeError, ValidationError)):
            IcebergTableManager(
                catalog_plugin=mock_catalog_plugin,
                storage_plugin="not a plugin",  # type: ignore[arg-type]
            )


class TestIcebergTableManagerProperties:
    """Tests for IcebergTableManager properties."""

    @pytest.mark.requirement("FR-008")
    def test_catalog_property(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test catalog property returns connected catalog."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # catalog should be the result of connect()
        assert manager.catalog is manager._catalog

    @pytest.mark.requirement("FR-010")
    def test_fileio_property(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test fileio property returns storage FileIO."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        assert manager.fileio is manager._fileio

    @pytest.mark.requirement("FR-008")
    def test_config_property(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test config property returns manager configuration."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig

        config = IcebergTableManagerConfig(max_commit_retries=7)

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        assert manager.config is config
        assert manager.config.max_commit_retries == 7


class TestIcebergTableManagerConnectionHandling:
    """Tests for connection error handling during initialization."""

    @pytest.mark.requirement("FR-009")
    def test_init_handles_catalog_connection_error(
        self,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager handles catalog connection errors."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IcebergError

        # Create a mock plugin that raises on connect
        failing_catalog = MagicMock()
        failing_catalog.name = "failing-catalog"
        failing_catalog.connect.side_effect = ConnectionError("Connection refused")

        with pytest.raises((ConnectionError, IcebergError)):
            IcebergTableManager(
                catalog_plugin=failing_catalog,
                storage_plugin=mock_storage_plugin,
            )

    @pytest.mark.requirement("FR-010")
    def test_init_handles_fileio_retrieval_error(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test IcebergTableManager handles FileIO retrieval errors."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IcebergError

        # Create a mock plugin that raises on get_pyiceberg_fileio
        failing_storage = MagicMock()
        failing_storage.name = "failing-storage"
        failing_storage.get_pyiceberg_fileio.side_effect = RuntimeError("FileIO unavailable")

        with pytest.raises((RuntimeError, IcebergError)):
            IcebergTableManager(
                catalog_plugin=mock_catalog_plugin,
                storage_plugin=failing_storage,
            )
