"""Unit tests for compute configuration models.

Tests the Pydantic models in compute_config.py for validation,
serialization, and edge cases.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from floe_core.compute_config import (
    AttachConfig,
    CatalogConfig,
    ComputeConfig,
    ConnectionResult,
    ConnectionStatus,
    DuckDBConfig,
    ResourceSpec,
    WORKLOAD_PRESETS,
)


class TestConnectionStatus:
    """Test ConnectionStatus enum."""

    @pytest.mark.requirement("001-FR-007")
    def test_connection_status_values(self) -> None:
        """Test ConnectionStatus has all expected values."""
        assert ConnectionStatus.HEALTHY.value == "healthy"
        assert ConnectionStatus.DEGRADED.value == "degraded"
        assert ConnectionStatus.UNHEALTHY.value == "unhealthy"

    @pytest.mark.requirement("001-FR-007")
    def test_connection_status_from_string(self) -> None:
        """Test ConnectionStatus can be created from string value."""
        assert ConnectionStatus("healthy") == ConnectionStatus.HEALTHY
        assert ConnectionStatus("degraded") == ConnectionStatus.DEGRADED
        assert ConnectionStatus("unhealthy") == ConnectionStatus.UNHEALTHY


class TestConnectionResult:
    """Test ConnectionResult Pydantic model."""

    @pytest.mark.requirement("001-FR-007")
    def test_connection_result_minimal(self) -> None:
        """Test ConnectionResult with minimal fields."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=23.5,
        )
        assert result.status == ConnectionStatus.HEALTHY
        assert result.latency_ms == pytest.approx(23.5)
        assert result.message == ""
        assert result.warnings == []

    @pytest.mark.requirement("001-FR-007")
    def test_connection_result_full(self) -> None:
        """Test ConnectionResult with all fields."""
        result = ConnectionResult(
            status=ConnectionStatus.DEGRADED,
            latency_ms=100.0,
            message="Extension not loaded",
            warnings=["iceberg extension missing", "httpfs extension missing"],
        )
        assert result.status == ConnectionStatus.DEGRADED
        assert result.latency_ms == pytest.approx(100.0)
        assert result.message == "Extension not loaded"
        assert len(result.warnings) == 2

    @pytest.mark.requirement("001-FR-007")
    def test_connection_result_frozen(self) -> None:
        """Test ConnectionResult is immutable."""
        result = ConnectionResult(
            status=ConnectionStatus.HEALTHY,
            latency_ms=10.0,
        )
        with pytest.raises(ValidationError):
            result.status = ConnectionStatus.UNHEALTHY  # type: ignore[misc]

    @pytest.mark.requirement("001-FR-007")
    def test_connection_result_negative_latency_invalid(self) -> None:
        """Test ConnectionResult rejects negative latency."""
        with pytest.raises(ValidationError, match="latency_ms"):
            ConnectionResult(
                status=ConnectionStatus.HEALTHY,
                latency_ms=-1.0,
            )


class TestResourceSpec:
    """Test ResourceSpec Pydantic model."""

    @pytest.mark.requirement("001-FR-008")
    def test_resource_spec_defaults(self) -> None:
        """Test ResourceSpec has sensible defaults."""
        spec = ResourceSpec()
        assert spec.cpu_request == "100m"
        assert spec.cpu_limit == "1000m"
        assert spec.memory_request == "256Mi"
        assert spec.memory_limit == "1Gi"

    @pytest.mark.requirement("001-FR-008")
    def test_resource_spec_custom_values(self) -> None:
        """Test ResourceSpec with custom values."""
        spec = ResourceSpec(
            cpu_request="500m",
            cpu_limit="2000m",
            memory_request="1Gi",
            memory_limit="4Gi",
            ephemeral_storage_request="500Mi",
            ephemeral_storage_limit="2Gi",
        )
        assert spec.cpu_request == "500m"
        assert spec.memory_limit == "4Gi"
        assert spec.ephemeral_storage_limit == "2Gi"

    @pytest.mark.requirement("001-FR-008")
    def test_resource_spec_frozen(self) -> None:
        """Test ResourceSpec is immutable."""
        spec = ResourceSpec()
        with pytest.raises(ValidationError):
            spec.cpu_request = "1000m"  # type: ignore[misc]


class TestWorkloadPresets:
    """Test WORKLOAD_PRESETS constant."""

    @pytest.mark.requirement("001-FR-008")
    def test_workload_presets_exist(self) -> None:
        """Test all expected presets exist."""
        assert "small" in WORKLOAD_PRESETS
        assert "medium" in WORKLOAD_PRESETS
        assert "large" in WORKLOAD_PRESETS

    @pytest.mark.requirement("001-FR-008")
    def test_workload_presets_are_resource_spec(self) -> None:
        """Test presets are ResourceSpec instances."""
        for preset_name, spec in WORKLOAD_PRESETS.items():
            assert isinstance(spec, ResourceSpec), f"{preset_name} should be ResourceSpec"

    @pytest.mark.requirement("001-FR-008")
    def test_workload_presets_scaling(self) -> None:
        """Test larger presets have more resources."""
        small = WORKLOAD_PRESETS["small"]
        medium = WORKLOAD_PRESETS["medium"]
        large = WORKLOAD_PRESETS["large"]

        def parse_memory(mem: str) -> int:
            """Parse memory string to MiB."""
            if mem.endswith("Gi"):
                return int(mem[:-2]) * 1024
            if mem.endswith("Mi"):
                return int(mem[:-2])
            return int(mem)

        small_mem = parse_memory(small.memory_limit)
        medium_mem = parse_memory(medium.memory_limit)
        large_mem = parse_memory(large.memory_limit)

        assert small_mem < medium_mem < large_mem


class TestComputeConfig:
    """Test ComputeConfig Pydantic model."""

    @pytest.mark.requirement("001-FR-005")
    def test_compute_config_minimal(self) -> None:
        """Test ComputeConfig with minimal required fields."""
        config = ComputeConfig(plugin="duckdb")
        assert config.plugin == "duckdb"
        assert config.timeout_seconds == 3600
        assert config.threads == 4

    @pytest.mark.requirement("001-FR-005")
    def test_compute_config_with_connection(self) -> None:
        """Test ComputeConfig with connection settings."""
        config = ComputeConfig(
            plugin="snowflake",
            threads=8,
            connection={
                "account": "my_account",
                "database": "analytics",
            },
        )
        assert config.plugin == "snowflake"
        assert config.threads == 8
        assert config.connection["account"] == "my_account"

    @pytest.mark.requirement("001-FR-005")
    def test_compute_config_with_credentials(self) -> None:
        """Test ComputeConfig handles SecretStr credentials."""
        config = ComputeConfig(
            plugin="snowflake",
            credentials={
                "password": SecretStr("secret123"),
            },
        )
        # SecretStr should mask the value
        assert "secret123" not in str(config.credentials["password"])
        assert config.credentials["password"].get_secret_value() == "secret123"

    @pytest.mark.requirement("001-FR-005")
    def test_compute_config_empty_plugin_invalid(self) -> None:
        """Test ComputeConfig rejects empty plugin name."""
        with pytest.raises(ValidationError, match="plugin"):
            ComputeConfig(plugin="")

    @pytest.mark.requirement("001-FR-005")
    def test_compute_config_timeout_bounds(self) -> None:
        """Test ComputeConfig timeout validation."""
        # Valid timeout
        config = ComputeConfig(plugin="duckdb", timeout_seconds=60)
        assert config.timeout_seconds == 60

        # Too low
        with pytest.raises(ValidationError, match="timeout_seconds"):
            ComputeConfig(plugin="duckdb", timeout_seconds=0)

        # Too high
        with pytest.raises(ValidationError, match="timeout_seconds"):
            ComputeConfig(plugin="duckdb", timeout_seconds=86401)


class TestAttachConfig:
    """Test AttachConfig Pydantic model."""

    @pytest.mark.requirement("001-FR-009")
    def test_attach_config_minimal(self) -> None:
        """Test AttachConfig with required fields."""
        attach = AttachConfig(
            path="iceberg:polaris",
            alias="ice",
        )
        assert attach.path == "iceberg:polaris"
        assert attach.alias == "ice"
        assert attach.type == "iceberg"

    @pytest.mark.requirement("001-FR-009")
    def test_attach_config_with_options(self) -> None:
        """Test AttachConfig with additional options."""
        attach = AttachConfig(
            path="iceberg:polaris",
            alias="ice",
            options={
                "catalog_uri": "http://polaris:8181/api/catalog",
                "warehouse": "floe_warehouse",
            },
        )
        assert attach.options["catalog_uri"] == "http://polaris:8181/api/catalog"

    @pytest.mark.requirement("001-FR-009")
    def test_attach_config_frozen(self) -> None:
        """Test AttachConfig is immutable."""
        attach = AttachConfig(path="iceberg:polaris", alias="ice")
        with pytest.raises(ValidationError):
            attach.alias = "new_alias"  # type: ignore[misc]


class TestDuckDBConfig:
    """Test DuckDBConfig Pydantic model."""

    @pytest.mark.requirement("001-FR-006")
    def test_duckdb_config_defaults(self) -> None:
        """Test DuckDBConfig has DuckDB-specific defaults."""
        config = DuckDBConfig()
        assert config.plugin == "duckdb"
        assert config.path == ":memory:"
        assert config.memory_limit == "4GB"
        assert config.extensions == []

    @pytest.mark.requirement("001-FR-006")
    def test_duckdb_config_custom(self) -> None:
        """Test DuckDBConfig with custom values."""
        config = DuckDBConfig(
            path="/data/analytics.duckdb",
            memory_limit="8GB",
            extensions=["iceberg", "httpfs"],
            threads=8,
        )
        assert config.path == "/data/analytics.duckdb"
        assert config.memory_limit == "8GB"
        assert "iceberg" in config.extensions
        assert config.threads == 8

    @pytest.mark.requirement("001-FR-006")
    def test_duckdb_config_with_attach(self) -> None:
        """Test DuckDBConfig with Iceberg attach configuration."""
        attach = AttachConfig(
            path="iceberg:polaris",
            alias="ice",
            options={"catalog_uri": "http://polaris:8181/api/catalog"},
        )
        config = DuckDBConfig(
            path=":memory:",
            attach=[attach],
        )
        assert len(config.attach) == 1
        assert config.attach[0].alias == "ice"

    @pytest.mark.requirement("001-FR-006")
    def test_duckdb_config_memory_limit_validation(self) -> None:
        """Test DuckDBConfig validates memory_limit format."""
        # Valid formats
        DuckDBConfig(memory_limit="4GB")
        DuckDBConfig(memory_limit="512MB")

        # Invalid format
        with pytest.raises(ValidationError, match="memory_limit must end with GB or MB"):
            DuckDBConfig(memory_limit="4G")

        with pytest.raises(ValidationError, match="memory_limit must end with GB or MB"):
            DuckDBConfig(memory_limit="4096")

    @pytest.mark.requirement("001-FR-006")
    def test_duckdb_config_plugin_fixed(self) -> None:
        """Test DuckDBConfig plugin is always 'duckdb'."""
        config = DuckDBConfig()
        assert config.plugin == "duckdb"


class TestCatalogConfig:
    """Test CatalogConfig Pydantic model."""

    @pytest.mark.requirement("001-FR-009")
    def test_catalog_config_minimal(self) -> None:
        """Test CatalogConfig with required fields."""
        catalog = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
        )
        assert catalog.catalog_type == "rest"
        assert catalog.catalog_uri == "http://polaris:8181/api/catalog"
        assert catalog.catalog_name == "floe"
        assert catalog.warehouse is None

    @pytest.mark.requirement("001-FR-009")
    def test_catalog_config_with_warehouse(self) -> None:
        """Test CatalogConfig with warehouse path."""
        catalog = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
            warehouse="s3://floe-bucket/warehouse",
        )
        assert catalog.warehouse == "s3://floe-bucket/warehouse"

    @pytest.mark.requirement("001-FR-009")
    def test_catalog_config_with_credentials(self) -> None:
        """Test CatalogConfig handles OAuth2 credentials."""
        catalog = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
            credentials={
                "client_id": SecretStr("my_client_id"),
                "client_secret": SecretStr("my_secret"),
            },
        )
        assert catalog.credentials["client_id"].get_secret_value() == "my_client_id"
        # Secret should be masked in string representation
        assert "my_secret" not in str(catalog.credentials["client_secret"])

    @pytest.mark.requirement("001-FR-009")
    def test_catalog_config_frozen(self) -> None:
        """Test CatalogConfig is immutable."""
        catalog = CatalogConfig(
            catalog_type="rest",
            catalog_uri="http://polaris:8181/api/catalog",
            catalog_name="floe",
        )
        with pytest.raises(ValidationError):
            catalog.catalog_name = "new_name"  # type: ignore[misc]
