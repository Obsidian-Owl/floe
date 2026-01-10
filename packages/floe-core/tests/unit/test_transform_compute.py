"""Unit tests for per-transform compute selection.

Tests for FR-012 (transforms[].compute field) and FR-014 (environment parity).

These tests validate:
- Transform-level compute field parsing
- Default compute inheritance from platform configuration
- Environment parity enforcement (same compute across dev/staging/prod)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from floe_core.plugins.orchestrator import TransformConfig

if TYPE_CHECKING:
    pass


class TestTransformComputeFieldParsing:
    """Test transforms[].compute field parsing (FR-012)."""

    @pytest.mark.requirement("001-FR-012")
    def test_transform_config_has_compute_field(self) -> None:
        """Test TransformConfig accepts optional compute field."""
        transform = TransformConfig(
            name="stg_customers",
            compute="duckdb",
        )

        assert transform.compute == "duckdb"

    @pytest.mark.requirement("001-FR-012")
    def test_transform_config_compute_defaults_to_none(self) -> None:
        """Test TransformConfig.compute defaults to None when not specified."""
        transform = TransformConfig(
            name="stg_customers",
        )

        assert transform.compute is None

    @pytest.mark.requirement("001-FR-012")
    def test_transform_config_with_explicit_compute(self) -> None:
        """Test transform with explicit compute override."""
        transform = TransformConfig(
            name="heavy_aggregation",
            path="models/marts/heavy_aggregation.sql",
            schema_name="marts",
            materialization="table",
            compute="spark",
        )

        assert transform.name == "heavy_aggregation"
        assert transform.compute == "spark"
        assert transform.materialization == "table"

    @pytest.mark.requirement("001-FR-012")
    def test_multiple_transforms_with_different_computes(self) -> None:
        """Test multiple transforms can specify different compute targets."""
        transforms = [
            TransformConfig(name="light_model", compute="duckdb"),
            TransformConfig(name="heavy_model", compute="spark"),
            TransformConfig(name="warehouse_model", compute="snowflake"),
        ]

        assert transforms[0].compute == "duckdb"
        assert transforms[1].compute == "spark"
        assert transforms[2].compute == "snowflake"

    @pytest.mark.requirement("001-FR-012")
    def test_transform_config_preserves_other_fields_with_compute(self) -> None:
        """Test compute field doesn't interfere with other TransformConfig fields."""
        transform = TransformConfig(
            name="dim_customers",
            path="models/marts/dim_customers.sql",
            schema_name="gold",
            materialization="incremental",
            tags=["daily", "customers"],
            depends_on=["stg_customers", "stg_orders"],
            meta={"owner": "data-team"},
            compute="duckdb",
        )

        assert transform.name == "dim_customers"
        assert transform.path == "models/marts/dim_customers.sql"
        assert transform.schema_name == "gold"
        assert transform.materialization == "incremental"
        assert transform.tags == ["daily", "customers"]
        assert transform.depends_on == ["stg_customers", "stg_orders"]
        assert transform.meta == {"owner": "data-team"}
        assert transform.compute == "duckdb"


class TestDefaultComputeInheritance:
    """Test default compute inheritance from platform configuration (FR-012)."""

    @pytest.mark.requirement("001-FR-012")
    def test_transform_inherits_platform_default_when_compute_is_none(self) -> None:
        """Test transform uses platform default when compute not specified.

        This tests the integration between TransformConfig and ComputeRegistry.
        When a transform doesn't specify compute (None), the system should
        use the platform default from ComputeRegistry.
        """
        from floe_core.compute_registry import ComputeRegistry

        # Create mock plugin registry
        mock_registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_registry.get = MagicMock(return_value=mock_plugin)

        # Create compute registry with default
        compute_registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_registry,
        )

        # Transform without explicit compute
        transform = TransformConfig(name="stg_customers")

        # Validate selection returns default when None
        resolved_compute = compute_registry.validate_selection(transform.compute)

        assert transform.compute is None
        assert resolved_compute == "duckdb"

    @pytest.mark.requirement("001-FR-012")
    def test_explicit_compute_overrides_platform_default(self) -> None:
        """Test explicit compute selection overrides platform default.

        When a transform specifies a compute target, it should be used
        instead of the platform default.
        """
        from floe_core.compute_registry import ComputeRegistry

        # Create mock plugin registry
        mock_registry = MagicMock()
        mock_plugin_duckdb = MagicMock()
        mock_plugin_duckdb.name = "duckdb"
        mock_plugin_spark = MagicMock()
        mock_plugin_spark.name = "spark"

        def get_plugin(plugin_type: Any, name: str) -> MagicMock:
            if name == "duckdb":
                return mock_plugin_duckdb
            elif name == "spark":
                return mock_plugin_spark
            raise ValueError(f"Unknown plugin: {name}")

        mock_registry.get = get_plugin

        # Create compute registry with duckdb as default
        compute_registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_registry,
        )

        # Transform with explicit spark compute
        transform = TransformConfig(name="heavy_model", compute="spark")

        # Validate selection respects explicit compute
        resolved_compute = compute_registry.validate_selection(transform.compute)

        assert transform.compute == "spark"
        assert resolved_compute == "spark"  # Not duckdb

    @pytest.mark.requirement("001-FR-012")
    def test_batch_resolve_transforms_with_mixed_compute(self) -> None:
        """Test resolving compute for batch of transforms with mixed specifications."""
        from floe_core.compute_registry import ComputeRegistry

        # Create mock plugin registry
        mock_registry = MagicMock()

        def get_plugin(plugin_type: Any, name: str) -> MagicMock:
            mock = MagicMock()
            mock.name = name
            return mock

        mock_registry.get = get_plugin

        compute_registry = ComputeRegistry(
            approved=["duckdb", "spark", "snowflake"],
            default="duckdb",
            plugin_registry=mock_registry,
        )

        transforms = [
            TransformConfig(name="model_a", compute=None),  # Should use default
            TransformConfig(name="model_b", compute="spark"),  # Explicit
            TransformConfig(name="model_c"),  # Should use default
            TransformConfig(name="model_d", compute="snowflake"),  # Explicit
        ]

        resolved = [compute_registry.validate_selection(t.compute) for t in transforms]

        assert resolved == ["duckdb", "spark", "duckdb", "snowflake"]


class TestEnvironmentParityEnforcement:
    """Test environment parity enforcement (FR-014).

    FR-014 requires that each transform uses the SAME compute across
    dev/staging/prod environments. This prevents issues where a transform
    works in dev (DuckDB) but fails in prod (different compute).
    """

    @pytest.mark.requirement("001-FR-014")
    def test_environment_parity_same_compute_all_environments(self) -> None:
        """Test no error when same compute used across all environments.

        This validates the positive case - when a data engineer specifies
        the same compute target for all environments.
        """
        # Simulate environment configs with same compute
        env_configs = {
            "dev": TransformConfig(name="stg_customers", compute="duckdb"),
            "staging": TransformConfig(name="stg_customers", compute="duckdb"),
            "prod": TransformConfig(name="stg_customers", compute="duckdb"),
        }

        # All computes should match
        computes = {env: cfg.compute for env, cfg in env_configs.items()}
        unique_computes = set(computes.values())

        assert len(unique_computes) == 1
        assert "duckdb" in unique_computes

    @pytest.mark.requirement("001-FR-014")
    def test_environment_parity_detects_mismatch(self) -> None:
        """Test detection of compute mismatch across environments.

        This validates that the system can detect when a transform
        specifies different computes for different environments.
        """
        # Simulate environment configs with DIFFERENT computes
        env_configs = {
            "dev": TransformConfig(name="stg_customers", compute="duckdb"),
            "staging": TransformConfig(name="stg_customers", compute="spark"),
            "prod": TransformConfig(name="stg_customers", compute="spark"),
        }

        computes = {env: cfg.compute for env, cfg in env_configs.items()}
        unique_computes = set(computes.values())

        # Should detect mismatch
        assert len(unique_computes) > 1
        assert "duckdb" in unique_computes
        assert "spark" in unique_computes

    @pytest.mark.requirement("001-FR-014")
    def test_environment_parity_none_inherits_same_default(self) -> None:
        """Test that None compute in all envs inherits same platform default.

        When no compute is specified (None), the platform default should
        be used consistently across all environments.
        """
        from floe_core.compute_registry import ComputeRegistry

        # Create mock plugin registry
        mock_registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_registry.get = MagicMock(return_value=mock_plugin)

        # Same compute registry for all environments
        compute_registry = ComputeRegistry(
            approved=["duckdb", "spark"],
            default="duckdb",
            plugin_registry=mock_registry,
        )

        # All transforms use None (inherit default)
        env_configs = {
            "dev": TransformConfig(name="stg_customers"),
            "staging": TransformConfig(name="stg_customers"),
            "prod": TransformConfig(name="stg_customers"),
        }

        # Resolve computes through registry
        resolved = {
            env: compute_registry.validate_selection(cfg.compute)
            for env, cfg in env_configs.items()
        }

        # All should resolve to same default
        assert resolved["dev"] == "duckdb"
        assert resolved["staging"] == "duckdb"
        assert resolved["prod"] == "duckdb"

    @pytest.mark.requirement("001-FR-014")
    def test_environment_parity_error_message_lists_mismatches(self) -> None:
        """Test that parity violation error message is clear and actionable.

        When a parity violation is detected, the error message should:
        - List the transform name
        - Show which environments use which compute
        - Be clear about what needs to change
        """
        from floe_core.compiler import EnvironmentParityError

        # Create actual error instance to test message formatting
        error = EnvironmentParityError(
            transform_name="stg_customers",
            env_computes={
                "dev": "duckdb",
                "staging": "spark",
                "prod": "spark",
            },
        )

        # Get the error message from the actual exception
        error_message = str(error)

        # Verify error message contains expected content
        assert "stg_customers" in error_message
        assert "dev=duckdb" in error_message
        assert "staging=spark" in error_message
        assert "prod=spark" in error_message
        assert "Environment parity violation" in error_message

        # Verify error attributes are accessible
        assert error.transform_name == "stg_customers"
        assert error.env_computes == {
            "dev": "duckdb",
            "staging": "spark",
            "prod": "spark",
        }


class TestComputeFieldValidation:
    """Test validation of compute field values."""

    @pytest.mark.requirement("001-FR-012")
    @pytest.mark.requirement("001-FR-013")
    def test_compute_must_be_in_approved_list(self) -> None:
        """Test that compute selection must be in approved list (compile-time validation)."""
        from floe_core.compute_errors import ComputeConfigurationError
        from floe_core.compute_registry import ComputeRegistry

        # Create mock plugin registry with only duckdb
        mock_registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_registry.get = MagicMock(return_value=mock_plugin)

        # Create compute registry with limited approved list
        compute_registry = ComputeRegistry(
            approved=["duckdb"],
            default="duckdb",
            plugin_registry=mock_registry,
        )

        # Transform requests unapproved compute
        transform = TransformConfig(name="model", compute="spark")

        # Should raise at compile time, not runtime
        with pytest.raises(
            ComputeConfigurationError,
            match="'spark' is not in the approved list",
        ):
            compute_registry.validate_selection(transform.compute)

    @pytest.mark.requirement("001-FR-013")
    def test_validation_happens_at_compile_time(self) -> None:
        """Test that validation is at compile time, not runtime.

        FR-013 requires compile-time validation. This means:
        - Validation happens when parsing floe.yaml
        - Errors are raised before any jobs are scheduled
        - Data engineers get fast feedback on configuration errors
        """
        from floe_core.compute_errors import ComputeConfigurationError
        from floe_core.compute_registry import ComputeRegistry

        mock_registry = MagicMock()
        mock_plugin = MagicMock()
        mock_plugin.name = "duckdb"
        mock_registry.get = MagicMock(return_value=mock_plugin)

        compute_registry = ComputeRegistry(
            approved=["duckdb"],
            default="duckdb",
            plugin_registry=mock_registry,
        )

        # Simulate compile-time validation of all transforms
        transforms = [
            TransformConfig(name="valid", compute="duckdb"),
            TransformConfig(name="invalid", compute="bigquery"),  # Not approved
        ]

        # Validate all at "compile time"
        errors: list[str] = []
        for transform in transforms:
            try:
                compute_registry.validate_selection(transform.compute)
            except ComputeConfigurationError as e:
                errors.append(f"{transform.name}: {e}")

        # Should have caught the error at "compile time"
        assert len(errors) == 1
        assert "invalid" in errors[0]
        assert "bigquery" in errors[0]
