"""Unit tests for ComputeRegistry.

Tests the ComputeRegistry class for managing approved compute targets,
default selection, and hierarchical governance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.compute_errors import ComputeConfigurationError
from floe_core.compute_registry import ComputeRegistry
from floe_core.plugin_types import PluginType


class MockComputePlugin:
    """Mock compute plugin for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


@pytest.fixture
def mock_plugin_registry() -> MagicMock:
    """Create a mock PluginRegistry with duckdb and spark plugins."""
    registry = MagicMock()

    # Create mock plugins
    duckdb_plugin = MockComputePlugin("duckdb")
    spark_plugin = MockComputePlugin("spark")
    snowflake_plugin = MockComputePlugin("snowflake")

    def get_plugin(plugin_type: PluginType, name: str) -> Any:
        plugins = {
            "duckdb": duckdb_plugin,
            "spark": spark_plugin,
            "snowflake": snowflake_plugin,
        }
        if name in plugins:
            return plugins[name]
        from floe_core.plugin_errors import PluginNotFoundError

        raise PluginNotFoundError(plugin_type, name)

    registry.get = get_plugin
    return registry


class TestComputeRegistryInitialization:
    """Test ComputeRegistry initialization and validation."""

    @pytest.mark.requirement("001-FR-010")
    def test_init_with_valid_config(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test successful initialization with valid approved list and default."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.approved == ["duckdb", "spark"]
        assert registry.default == "duckdb"

    @pytest.mark.requirement("001-FR-010")
    def test_init_with_single_approved(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test initialization with single approved compute."""
        registry = ComputeRegistry(
            approved=["duckdb"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.approved == ["duckdb"]
        assert registry.default == "duckdb"

    @pytest.mark.requirement("001-FR-010")
    def test_init_empty_approved_raises_error(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test empty approved list raises ComputeConfigurationError."""
        with pytest.raises(
            ComputeConfigurationError,
            match="Approved compute list cannot be empty",
        ):
            ComputeRegistry(
                approved=[],
                default="duckdb",
                plugin_registry=mock_plugin_registry,
            )

    @pytest.mark.requirement("001-FR-011")
    def test_init_default_not_in_approved_raises_error(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test default not in approved list raises ComputeConfigurationError."""
        with pytest.raises(
            ComputeConfigurationError,
            match="Default compute 'bigquery' must be in approved list",
        ):
            ComputeRegistry(
                approved=["duckdb", "spark"],
                default="bigquery",
                plugin_registry=mock_plugin_registry,
            )

    @pytest.mark.requirement("001-FR-010")
    def test_init_with_undiscovered_plugin_raises_error(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test approved plugin not discoverable raises ComputeConfigurationError."""
        with pytest.raises(
            ComputeConfigurationError,
            match="Approved compute plugins not found.*bigquery",
        ):
            ComputeRegistry(
                approved=["duckdb", "bigquery"],
                default="duckdb",
                plugin_registry=mock_plugin_registry,
            )


class TestComputeRegistryProperties:
    """Test ComputeRegistry property accessors."""

    @pytest.mark.requirement("001-FR-010")
    def test_approved_returns_copy(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test approved property returns a copy of the list."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        approved_list = registry.approved
        approved_list.append("bigquery")  # Modify the returned list

        # Original should be unchanged
        assert registry.approved == ["duckdb", "spark"]

    @pytest.mark.requirement("001-FR-011")
    def test_default_property(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test default property returns the default compute name."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="spark",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.default == "spark"


class TestComputeRegistryGet:
    """Test ComputeRegistry get method."""

    @pytest.mark.requirement("001-FR-010")
    def test_get_approved_plugin(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test getting an approved compute plugin."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        plugin = registry.get("duckdb")
        assert plugin.name == "duckdb"

    @pytest.mark.requirement("001-FR-010")
    def test_get_unapproved_plugin_raises_error(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test getting unapproved plugin raises ComputeConfigurationError."""
        registry = ComputeRegistry(
            approved=["duckdb"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        with pytest.raises(
            ComputeConfigurationError,
            match="Compute 'spark' is not in the approved list",
        ):
            registry.get("spark")

    @pytest.mark.requirement("001-FR-011")
    def test_get_default(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test get_default returns the default plugin."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="spark",
            plugin_registry=mock_plugin_registry,
        )

        plugin = registry.get_default()
        assert plugin.name == "spark"


class TestComputeRegistryIsApproved:
    """Test ComputeRegistry is_approved method."""

    @pytest.mark.requirement("001-FR-013")
    def test_is_approved_returns_true_for_approved(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test is_approved returns True for approved compute."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.is_approved("duckdb") is True
        assert registry.is_approved("spark") is True

    @pytest.mark.requirement("001-FR-013")
    def test_is_approved_returns_false_for_unapproved(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test is_approved returns False for unapproved compute."""
        registry = ComputeRegistry(
            approved=["duckdb"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.is_approved("spark") is False
        assert registry.is_approved("bigquery") is False


class TestComputeRegistryListApproved:
    """Test ComputeRegistry list_approved method."""

    @pytest.mark.requirement("001-FR-010")
    def test_list_approved_returns_all_plugins(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test list_approved returns all approved compute plugins."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        plugins = registry.list_approved()
        names = [p.name for p in plugins]

        assert len(plugins) == 2
        assert "duckdb" in names
        assert "spark" in names


class TestComputeRegistryValidateSelection:
    """Test ComputeRegistry validate_selection method."""

    @pytest.mark.requirement("001-FR-012")
    def test_validate_selection_returns_valid_compute(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test validate_selection returns validated compute name."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.validate_selection("spark") == "spark"

    @pytest.mark.requirement("001-FR-012")
    def test_validate_selection_returns_default_for_none(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test validate_selection returns default when compute is None."""
        registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        assert registry.validate_selection(None) == "duckdb"

    @pytest.mark.requirement("001-FR-013")
    def test_validate_selection_raises_for_invalid(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test validate_selection raises error for unapproved compute."""
        registry = ComputeRegistry(
            approved=["duckdb"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        with pytest.raises(
            ComputeConfigurationError,
            match="Compute 'bigquery' is not in the approved list",
        ):
            registry.validate_selection("bigquery")


class TestComputeRegistryHierarchicalGovernance:
    """Test ComputeRegistry hierarchical governance (create_restricted)."""

    @pytest.mark.requirement("001-FR-015")
    def test_create_restricted_valid_subset(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test create_restricted with valid subset of approved."""
        enterprise = ComputeRegistry(
            approved=["duckdb", "spark", "snowflake"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        domain = enterprise.create_restricted(
            approved=["duckdb", "spark"],
            default="duckdb",
        )

        assert domain.approved == ["duckdb", "spark"]
        assert domain.default == "duckdb"

    @pytest.mark.requirement("001-FR-015")
    def test_create_restricted_inherits_default_when_allowed(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test create_restricted uses parent default when in child approved."""
        enterprise = ComputeRegistry(
            approved=["duckdb", "spark", "snowflake"],
            default="spark",
            plugin_registry=mock_plugin_registry,
        )

        domain = enterprise.create_restricted(
            approved=["spark", "snowflake"],
        )

        assert domain.default == "spark"  # Inherited from parent

    @pytest.mark.requirement("001-FR-015")
    def test_create_restricted_uses_first_when_default_excluded(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test create_restricted uses first approved when parent default excluded."""
        enterprise = ComputeRegistry(
            approved=["duckdb", "spark", "snowflake"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        domain = enterprise.create_restricted(
            approved=["spark", "snowflake"],
        )

        assert domain.default == "spark"  # First in approved list

    @pytest.mark.requirement("001-FR-016")
    def test_create_restricted_raises_for_invalid_subset(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test create_restricted raises error for non-subset approved list."""
        enterprise = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        with pytest.raises(
            ComputeConfigurationError,
            match=r"Compute targets \['bigquery'\] are not in the parent approved list",
        ):
            enterprise.create_restricted(
                approved=["duckdb", "bigquery"],
            )

    @pytest.mark.requirement("001-FR-016")
    def test_create_restricted_nested_hierarchy(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test nested hierarchical governance (Enterprise -> Domain -> Product)."""
        enterprise = ComputeRegistry(
            approved=["duckdb", "spark", "snowflake"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        domain = enterprise.create_restricted(
            approved=["duckdb", "spark"],
            default="duckdb",
        )

        product = domain.create_restricted(
            approved=["duckdb"],
            default="duckdb",
        )

        assert product.approved == ["duckdb"]
        assert product.default == "duckdb"

    @pytest.mark.requirement("001-FR-017")
    def test_create_restricted_error_message_includes_allowed(
        self,
        mock_plugin_registry: MagicMock,
    ) -> None:
        """Test governance violation error includes allowed options."""
        enterprise = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_plugin_registry,
        )

        with pytest.raises(
            ComputeConfigurationError,
            match=r"Parent allows: \['duckdb', 'spark'\]",
        ):
            enterprise.create_restricted(
                approved=["snowflake"],
            )
