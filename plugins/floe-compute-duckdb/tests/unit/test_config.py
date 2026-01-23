"""Unit tests for DuckDBConfig validation.

Tests the DuckDBConfig Pydantic model from floe_core, ensuring:
- Valid configurations are accepted
- Invalid memory_limit formats are rejected
- Default values work correctly
- Frozen model constraints are enforced
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from floe_core.compute_config import AttachConfig, DuckDBConfig
from pydantic import ValidationError

if TYPE_CHECKING:
    pass


class TestDuckDBConfigValidation:
    """Tests for DuckDBConfig Pydantic model validation."""

    def test_valid_config_minimal(self) -> None:
        """Test minimal valid DuckDBConfig with defaults."""
        config = DuckDBConfig()

        assert config.plugin == "duckdb"
        assert config.path == ":memory:"
        assert config.memory_limit == "4GB"
        assert config.extensions == []
        assert config.attach == []
        assert config.threads == 4
        assert config.timeout_seconds == 3600

    def test_valid_config_with_all_fields(self) -> None:
        """Test DuckDBConfig with all fields specified."""
        attach = AttachConfig(
            path="iceberg:polaris",
            alias="iceberg_catalog",
            type="iceberg",
            options={"catalog_uri": "http://polaris:8181/api/catalog"},
        )

        config = DuckDBConfig(
            path="/data/analytics.duckdb",
            memory_limit="8GB",
            extensions=["iceberg", "httpfs", "parquet"],
            attach=[attach],
            threads=8,
            timeout_seconds=7200,
        )

        assert config.plugin == "duckdb"
        assert config.path == "/data/analytics.duckdb"
        assert config.memory_limit == "8GB"
        assert config.extensions == ["iceberg", "httpfs", "parquet"]
        assert len(config.attach) == 1
        assert config.attach[0].alias == "iceberg_catalog"
        assert config.threads == 8
        assert config.timeout_seconds == 7200

    def test_valid_memory_limit_gigabytes(self) -> None:
        """Test valid memory_limit with GB suffix."""
        config = DuckDBConfig(memory_limit="16GB")
        assert config.memory_limit == "16GB"

    def test_valid_memory_limit_megabytes(self) -> None:
        """Test valid memory_limit with MB suffix."""
        config = DuckDBConfig(memory_limit="512MB")
        assert config.memory_limit == "512MB"

    def test_invalid_memory_limit_no_unit(self) -> None:
        """Test memory_limit without unit suffix is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DuckDBConfig(memory_limit="4096")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "memory_limit must end with GB or MB" in errors[0]["msg"]

    def test_invalid_memory_limit_wrong_unit(self) -> None:
        """Test memory_limit with invalid unit suffix is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DuckDBConfig(memory_limit="4KB")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "memory_limit must end with GB or MB" in errors[0]["msg"]

    def test_invalid_memory_limit_lowercase_unit(self) -> None:
        """Test memory_limit with lowercase unit is rejected (case-sensitive)."""
        with pytest.raises(ValidationError) as exc_info:
            DuckDBConfig(memory_limit="4gb")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "memory_limit must end with GB or MB" in errors[0]["msg"]

    def test_valid_in_memory_path(self) -> None:
        """Test in-memory path configuration."""
        config = DuckDBConfig(path=":memory:")
        assert config.path == ":memory:"

    def test_valid_file_path(self) -> None:
        """Test file-based path configuration."""
        config = DuckDBConfig(path="/tmp/test.duckdb")
        assert config.path == "/tmp/test.duckdb"

    def test_plugin_literal_enforcement(self) -> None:
        """Test that plugin field is fixed to 'duckdb'."""
        # Cannot set plugin to a different value
        with pytest.raises(ValidationError):
            DuckDBConfig(plugin="snowflake")  # type: ignore[arg-type]

    def test_threads_validation_minimum(self) -> None:
        """Test threads field minimum value (1)."""
        config = DuckDBConfig(threads=1)
        assert config.threads == 1

    def test_threads_validation_maximum(self) -> None:
        """Test threads field maximum value (64)."""
        config = DuckDBConfig(threads=64)
        assert config.threads == 64

    def test_threads_validation_below_minimum(self) -> None:
        """Test threads field below minimum is rejected."""
        with pytest.raises(ValidationError):
            DuckDBConfig(threads=0)

    def test_threads_validation_above_maximum(self) -> None:
        """Test threads field above maximum is rejected."""
        with pytest.raises(ValidationError):
            DuckDBConfig(threads=65)

    def test_timeout_validation_minimum(self) -> None:
        """Test timeout_seconds field minimum value (1)."""
        config = DuckDBConfig(timeout_seconds=1)
        assert config.timeout_seconds == 1

    def test_timeout_validation_maximum(self) -> None:
        """Test timeout_seconds field maximum value (86400 = 24 hours)."""
        config = DuckDBConfig(timeout_seconds=86400)
        assert config.timeout_seconds == 86400

    def test_timeout_validation_below_minimum(self) -> None:
        """Test timeout_seconds below minimum is rejected."""
        with pytest.raises(ValidationError):
            DuckDBConfig(timeout_seconds=0)

    def test_timeout_validation_above_maximum(self) -> None:
        """Test timeout_seconds above maximum is rejected."""
        with pytest.raises(ValidationError):
            DuckDBConfig(timeout_seconds=86401)


class TestAttachConfigValidation:
    """Tests for AttachConfig Pydantic model validation."""

    def test_valid_attach_config(self) -> None:
        """Test valid AttachConfig."""
        attach = AttachConfig(
            path="iceberg:polaris",
            alias="ice",
            type="iceberg",
            options={"warehouse": "floe_warehouse"},
        )

        assert attach.path == "iceberg:polaris"
        assert attach.alias == "ice"
        assert attach.type == "iceberg"
        assert attach.options == {"warehouse": "floe_warehouse"}

    def test_attach_config_required_fields(self) -> None:
        """Test AttachConfig requires path and alias."""
        with pytest.raises(ValidationError):
            AttachConfig(path="iceberg:test")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            AttachConfig(alias="test")  # type: ignore[call-arg]

    def test_attach_config_default_type(self) -> None:
        """Test AttachConfig default type is 'iceberg'."""
        attach = AttachConfig(path="iceberg:catalog", alias="ice")
        assert attach.type == "iceberg"

    def test_attach_config_frozen(self) -> None:
        """Test AttachConfig is frozen (immutable)."""
        attach = AttachConfig(path="iceberg:catalog", alias="ice")

        with pytest.raises(ValidationError):
            attach.path = "new_path"
