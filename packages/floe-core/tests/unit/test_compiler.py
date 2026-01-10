"""Unit tests for the compiler module.

Tests for FR-012 (per-transform compute selection), FR-013 (compile-time validation),
and FR-014 (environment parity enforcement).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from floe_core.compiler import (
    EnvironmentParityError,
    check_environment_parity,
    compile_transforms,
    resolve_transform_compute,
    resolve_transforms_compute,
    validate_environment_parity,
)
from floe_core.compute_errors import ComputeConfigurationError
from floe_core.compute_registry import ComputeRegistry
from floe_core.plugins.orchestrator import TransformConfig


class MockComputePlugin:
    """Mock compute plugin for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


@pytest.fixture
def mock_plugin_registry() -> MagicMock:
    """Create a mock PluginRegistry with duckdb, spark, and snowflake plugins."""
    registry = MagicMock()

    def get_plugin(plugin_type: Any, name: str) -> MockComputePlugin:
        plugins = {
            "duckdb": MockComputePlugin("duckdb"),
            "spark": MockComputePlugin("spark"),
            "snowflake": MockComputePlugin("snowflake"),
        }
        if name in plugins:
            return plugins[name]
        from floe_core.plugin_errors import PluginNotFoundError

        raise PluginNotFoundError(plugin_type, name)

    registry.get = get_plugin
    return registry


@pytest.fixture
def compute_registry(mock_plugin_registry: MagicMock) -> ComputeRegistry:
    """Create a ComputeRegistry with duckdb as default."""
    return ComputeRegistry(
        approved=["duckdb", "spark", "snowflake"],
        default="duckdb",
        plugin_registry=mock_plugin_registry,
    )


class TestResolveTransformCompute:
    """Test resolve_transform_compute function."""

    @pytest.mark.requirement("001-FR-012")
    def test_resolve_transform_compute_explicit(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test explicit compute is used when specified."""
        transform = TransformConfig(name="model", compute="spark")

        resolved = resolve_transform_compute(transform, compute_registry)

        assert resolved == "spark"

    @pytest.mark.requirement("001-FR-012")
    def test_resolve_transform_compute_default(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test platform default is used when compute is None."""
        transform = TransformConfig(name="model")

        resolved = resolve_transform_compute(transform, compute_registry)

        assert resolved == "duckdb"  # Platform default

    @pytest.mark.requirement("001-FR-013")
    def test_resolve_transform_compute_unapproved_raises(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test unapproved compute raises at compile time."""
        transform = TransformConfig(name="model", compute="bigquery")

        with pytest.raises(
            ComputeConfigurationError,
            match="'bigquery' is not in the approved list",
        ):
            resolve_transform_compute(transform, compute_registry)


class TestResolveTransformsCompute:
    """Test resolve_transforms_compute function."""

    @pytest.mark.requirement("001-FR-012")
    def test_resolve_transforms_compute_batch(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test batch resolution of multiple transforms."""
        transforms = [
            TransformConfig(name="model_a", compute=None),
            TransformConfig(name="model_b", compute="spark"),
            TransformConfig(name="model_c"),
            TransformConfig(name="model_d", compute="snowflake"),
        ]

        resolved = resolve_transforms_compute(transforms, compute_registry)

        assert resolved == {
            "model_a": "duckdb",  # Default
            "model_b": "spark",  # Explicit
            "model_c": "duckdb",  # Default
            "model_d": "snowflake",  # Explicit
        }


class TestCheckEnvironmentParity:
    """Test check_environment_parity function."""

    @pytest.mark.requirement("001-FR-014")
    def test_check_environment_parity_no_violation(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test no errors when same compute across all environments."""
        env_transforms = {
            "dev": [TransformConfig(name="model", compute="duckdb")],
            "staging": [TransformConfig(name="model", compute="duckdb")],
            "prod": [TransformConfig(name="model", compute="duckdb")],
        }

        errors = check_environment_parity(env_transforms, compute_registry)

        assert errors == []

    @pytest.mark.requirement("001-FR-014")
    def test_check_environment_parity_violation(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test error returned when compute differs across environments."""
        env_transforms = {
            "dev": [TransformConfig(name="model", compute="duckdb")],
            "staging": [TransformConfig(name="model", compute="spark")],
            "prod": [TransformConfig(name="model", compute="spark")],
        }

        errors = check_environment_parity(env_transforms, compute_registry)

        assert len(errors) == 1
        assert errors[0].transform_name == "model"
        assert errors[0].env_computes == {
            "dev": "duckdb",
            "staging": "spark",
            "prod": "spark",
        }

    @pytest.mark.requirement("001-FR-014")
    def test_check_environment_parity_multiple_violations(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test multiple transforms with violations are all reported."""
        env_transforms = {
            "dev": [
                TransformConfig(name="model_a", compute="duckdb"),
                TransformConfig(name="model_b", compute="spark"),
            ],
            "prod": [
                TransformConfig(name="model_a", compute="spark"),
                TransformConfig(name="model_b", compute="snowflake"),
            ],
        }

        errors = check_environment_parity(env_transforms, compute_registry)

        assert len(errors) == 2
        names = {e.transform_name for e in errors}
        assert names == {"model_a", "model_b"}

    @pytest.mark.requirement("001-FR-014")
    def test_check_environment_parity_none_inherits_same_default(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test None compute in all envs passes parity (same default)."""
        env_transforms = {
            "dev": [TransformConfig(name="model")],
            "staging": [TransformConfig(name="model")],
            "prod": [TransformConfig(name="model")],
        }

        errors = check_environment_parity(env_transforms, compute_registry)

        assert errors == []


class TestValidateEnvironmentParity:
    """Test validate_environment_parity function."""

    @pytest.mark.requirement("001-FR-014")
    def test_validate_environment_parity_success(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test no exception when parity is maintained."""
        env_transforms = {
            "dev": [TransformConfig(name="model", compute="spark")],
            "prod": [TransformConfig(name="model", compute="spark")],
        }

        # Should not raise
        validate_environment_parity(env_transforms, compute_registry)

    @pytest.mark.requirement("001-FR-014")
    def test_validate_environment_parity_raises(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test exception raised when parity is violated."""
        env_transforms = {
            "dev": [TransformConfig(name="model", compute="duckdb")],
            "prod": [TransformConfig(name="model", compute="spark")],
        }

        with pytest.raises(EnvironmentParityError) as exc_info:
            validate_environment_parity(env_transforms, compute_registry)

        assert exc_info.value.transform_name == "model"
        assert "Environment parity violation" in str(exc_info.value)


class TestEnvironmentParityError:
    """Test EnvironmentParityError class."""

    @pytest.mark.requirement("001-FR-014")
    def test_error_message_format(self) -> None:
        """Test error message includes all relevant details."""
        error = EnvironmentParityError(
            transform_name="stg_customers",
            env_computes={"dev": "duckdb", "staging": "spark", "prod": "spark"},
        )

        message = str(error)

        assert "stg_customers" in message
        assert "dev=duckdb" in message
        assert "staging=spark" in message
        assert "prod=spark" in message
        assert "Environment parity violation" in message

    @pytest.mark.requirement("001-FR-014")
    def test_error_is_compute_configuration_error(self) -> None:
        """Test EnvironmentParityError inherits from ComputeConfigurationError."""
        error = EnvironmentParityError(
            transform_name="model",
            env_computes={"dev": "duckdb", "prod": "spark"},
        )

        assert isinstance(error, ComputeConfigurationError)


class TestCompileTransforms:
    """Test compile_transforms function."""

    @pytest.mark.requirement("001-FR-012")
    def test_compile_transforms_resolves_none(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test compile_transforms fills in platform default for None compute."""
        transforms = [
            TransformConfig(name="model_a"),
            TransformConfig(name="model_b", compute="spark"),
        ]

        compiled = compile_transforms(transforms, compute_registry)

        assert compiled[0].name == "model_a"
        assert compiled[0].compute == "duckdb"  # Resolved from default
        assert compiled[1].name == "model_b"
        assert compiled[1].compute == "spark"  # Kept explicit

    @pytest.mark.requirement("001-FR-012")
    def test_compile_transforms_preserves_other_fields(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test compile_transforms preserves all other TransformConfig fields."""
        transforms = [
            TransformConfig(
                name="model",
                path="models/model.sql",
                schema_name="gold",
                materialization="incremental",
                tags=["daily"],
                depends_on=["upstream"],
                meta={"owner": "data-team"},
            ),
        ]

        compiled = compile_transforms(transforms, compute_registry)

        assert compiled[0].name == "model"
        assert compiled[0].path == "models/model.sql"
        assert compiled[0].schema_name == "gold"
        assert compiled[0].materialization == "incremental"
        assert compiled[0].tags == ["daily"]
        assert compiled[0].depends_on == ["upstream"]
        assert compiled[0].meta == {"owner": "data-team"}
        assert compiled[0].compute == "duckdb"  # Resolved

    @pytest.mark.requirement("001-FR-013")
    def test_compile_transforms_validates_at_compile_time(
        self,
        compute_registry: ComputeRegistry,
    ) -> None:
        """Test compile_transforms raises for unapproved compute."""
        transforms = [
            TransformConfig(name="valid", compute="duckdb"),
            TransformConfig(name="invalid", compute="bigquery"),
        ]

        with pytest.raises(ComputeConfigurationError, match="bigquery"):
            compile_transforms(transforms, compute_registry)
