"""Unit tests for floe-iceberg models and enumerations.

Tests the Pydantic models and enumerations defined in floe_iceberg.models.
"""

from __future__ import annotations

import re

import pytest

from floe_iceberg.models import (
    IDENTIFIER_PATTERN,
    CommitStrategy,
    CompactionStrategyType,
    FieldType,
    IcebergIOManagerConfig,
    IcebergTableManagerConfig,
    OperationType,
    PartitionTransform,
    SchemaChangeType,
    WriteMode,
)


# =============================================================================
# IDENTIFIER_PATTERN Tests
# =============================================================================


class TestIdentifierPattern:
    """Tests for IDENTIFIER_PATTERN constant."""

    @pytest.mark.requirement("FR-045")
    def test_pattern_exists(self) -> None:
        """Test IDENTIFIER_PATTERN is defined."""
        assert IDENTIFIER_PATTERN is not None
        assert isinstance(IDENTIFIER_PATTERN, str)

    @pytest.mark.requirement("FR-045")
    def test_valid_identifiers(self) -> None:
        """Test pattern matches valid identifiers."""
        valid_names = [
            "customers",
            "dim_product",
            "raw_data_v2",
            "A",
            "MyTable",
            "table123",
            "a_b_c",
        ]
        pattern = re.compile(IDENTIFIER_PATTERN)
        for name in valid_names:
            assert pattern.match(name), f"'{name}' should be a valid identifier"

    @pytest.mark.requirement("FR-045")
    def test_invalid_identifiers(self) -> None:
        """Test pattern rejects invalid identifiers."""
        invalid_names = [
            "123_table",  # starts with number
            "_private",  # starts with underscore
            "has-hyphen",  # contains hyphen
            "has space",  # contains space
            "",  # empty string
            "has.dot",  # contains dot
        ]
        pattern = re.compile(IDENTIFIER_PATTERN)
        for name in invalid_names:
            assert not pattern.match(name), f"'{name}' should be an invalid identifier"


# =============================================================================
# FieldType Enum Tests
# =============================================================================


class TestFieldType:
    """Tests for FieldType enumeration."""

    @pytest.mark.requirement("FR-001")
    def test_all_iceberg_types_defined(self) -> None:
        """Test all Iceberg primitive types are defined."""
        expected_types = {
            "boolean",
            "int",
            "long",
            "float",
            "double",
            "decimal",
            "date",
            "time",
            "timestamp",
            "timestamptz",
            "string",
            "uuid",
            "fixed",
            "binary",
        }
        actual_types = {t.value for t in FieldType}
        assert actual_types == expected_types

    @pytest.mark.requirement("FR-001")
    def test_string_value(self) -> None:
        """Test FieldType enum has string values."""
        assert FieldType.STRING.value == "string"
        assert FieldType.LONG.value == "long"
        assert FieldType.TIMESTAMPTZ.value == "timestamptz"

    @pytest.mark.requirement("FR-001")
    def test_enum_is_str_subclass(self) -> None:
        """Test FieldType can be used as string."""
        assert isinstance(FieldType.STRING, str)
        assert FieldType.STRING == "string"


# =============================================================================
# PartitionTransform Enum Tests
# =============================================================================


class TestPartitionTransform:
    """Tests for PartitionTransform enumeration."""

    @pytest.mark.requirement("FR-001")
    def test_all_transforms_defined(self) -> None:
        """Test all partition transforms are defined."""
        expected_transforms = {
            "identity",
            "year",
            "month",
            "day",
            "hour",
            "bucket",
            "truncate",
        }
        actual_transforms = {t.value for t in PartitionTransform}
        assert actual_transforms == expected_transforms

    @pytest.mark.requirement("FR-001")
    def test_temporal_transforms(self) -> None:
        """Test temporal transform values."""
        assert PartitionTransform.YEAR.value == "year"
        assert PartitionTransform.MONTH.value == "month"
        assert PartitionTransform.DAY.value == "day"
        assert PartitionTransform.HOUR.value == "hour"

    @pytest.mark.requirement("FR-001")
    def test_data_transforms(self) -> None:
        """Test data transform values."""
        assert PartitionTransform.IDENTITY.value == "identity"
        assert PartitionTransform.BUCKET.value == "bucket"
        assert PartitionTransform.TRUNCATE.value == "truncate"


# =============================================================================
# SchemaChangeType Enum Tests
# =============================================================================


class TestSchemaChangeType:
    """Tests for SchemaChangeType enumeration."""

    @pytest.mark.requirement("FR-002")
    def test_all_change_types_defined(self) -> None:
        """Test all schema change types are defined."""
        expected_types = {
            "add_column",
            "rename_column",
            "widen_type",
            "make_optional",
            "delete_column",
            "update_doc",
        }
        actual_types = {t.value for t in SchemaChangeType}
        assert actual_types == expected_types

    @pytest.mark.requirement("FR-002")
    def test_compatible_changes(self) -> None:
        """Test compatible change type values."""
        assert SchemaChangeType.ADD_COLUMN.value == "add_column"
        assert SchemaChangeType.RENAME_COLUMN.value == "rename_column"
        assert SchemaChangeType.WIDEN_TYPE.value == "widen_type"
        assert SchemaChangeType.MAKE_OPTIONAL.value == "make_optional"
        assert SchemaChangeType.UPDATE_DOC.value == "update_doc"

    @pytest.mark.requirement("FR-002")
    def test_incompatible_change(self) -> None:
        """Test incompatible change type value."""
        assert SchemaChangeType.DELETE_COLUMN.value == "delete_column"


# =============================================================================
# WriteMode Enum Tests
# =============================================================================


class TestWriteMode:
    """Tests for WriteMode enumeration."""

    @pytest.mark.requirement("FR-003")
    def test_all_modes_defined(self) -> None:
        """Test all write modes are defined."""
        expected_modes = {"append", "overwrite", "upsert"}
        actual_modes = {m.value for m in WriteMode}
        assert actual_modes == expected_modes

    @pytest.mark.requirement("FR-003")
    def test_mode_values(self) -> None:
        """Test write mode values."""
        assert WriteMode.APPEND.value == "append"
        assert WriteMode.OVERWRITE.value == "overwrite"
        assert WriteMode.UPSERT.value == "upsert"


# =============================================================================
# CommitStrategy Enum Tests
# =============================================================================


class TestCommitStrategy:
    """Tests for CommitStrategy enumeration."""

    @pytest.mark.requirement("FR-003")
    def test_all_strategies_defined(self) -> None:
        """Test all commit strategies are defined."""
        expected_strategies = {"fast_append", "merge_commit"}
        actual_strategies = {s.value for s in CommitStrategy}
        assert actual_strategies == expected_strategies

    @pytest.mark.requirement("FR-003")
    def test_strategy_values(self) -> None:
        """Test commit strategy values."""
        assert CommitStrategy.FAST_APPEND.value == "fast_append"
        assert CommitStrategy.MERGE_COMMIT.value == "merge_commit"


# =============================================================================
# OperationType Enum Tests
# =============================================================================


class TestOperationType:
    """Tests for OperationType enumeration."""

    @pytest.mark.requirement("FR-004")
    def test_all_operations_defined(self) -> None:
        """Test all operation types are defined."""
        expected_ops = {"append", "overwrite", "delete", "replace"}
        actual_ops = {o.value for o in OperationType}
        assert actual_ops == expected_ops

    @pytest.mark.requirement("FR-004")
    def test_operation_values(self) -> None:
        """Test operation type values."""
        assert OperationType.APPEND.value == "append"
        assert OperationType.OVERWRITE.value == "overwrite"
        assert OperationType.DELETE.value == "delete"
        assert OperationType.REPLACE.value == "replace"


# =============================================================================
# CompactionStrategyType Enum Tests
# =============================================================================


class TestCompactionStrategyType:
    """Tests for CompactionStrategyType enumeration."""

    @pytest.mark.requirement("FR-005")
    def test_all_strategies_defined(self) -> None:
        """Test all compaction strategies are defined."""
        expected_strategies = {"bin_pack", "sort"}
        actual_strategies = {s.value for s in CompactionStrategyType}
        assert actual_strategies == expected_strategies

    @pytest.mark.requirement("FR-005")
    def test_strategy_values(self) -> None:
        """Test compaction strategy values."""
        assert CompactionStrategyType.BIN_PACK.value == "bin_pack"
        assert CompactionStrategyType.SORT.value == "sort"


# =============================================================================
# IcebergTableManagerConfig Tests
# =============================================================================


class TestIcebergTableManagerConfig:
    """Tests for IcebergTableManagerConfig model."""

    @pytest.mark.requirement("FR-045")
    def test_default_values(self) -> None:
        """Test config has sensible defaults."""
        config = IcebergTableManagerConfig()
        assert config.max_commit_retries == 3
        assert config.retry_base_delay_seconds == pytest.approx(1.0)
        assert config.default_retention_days == 7
        assert config.min_snapshots_to_keep == 10
        assert config.default_commit_strategy == CommitStrategy.FAST_APPEND

    @pytest.mark.requirement("FR-045")
    def test_default_table_properties(self) -> None:
        """Test default table properties are set correctly."""
        config = IcebergTableManagerConfig()
        assert "write.format.default" in config.default_table_properties
        assert config.default_table_properties["write.format.default"] == "parquet"
        assert "write.target-file-size-bytes" in config.default_table_properties

    @pytest.mark.requirement("FR-045")
    def test_custom_values(self) -> None:
        """Test config accepts custom values."""
        config = IcebergTableManagerConfig(
            max_commit_retries=5,
            retry_base_delay_seconds=2.5,
            default_retention_days=30,
            min_snapshots_to_keep=20,
            default_commit_strategy=CommitStrategy.MERGE_COMMIT,
        )
        assert config.max_commit_retries == 5
        assert config.retry_base_delay_seconds == pytest.approx(2.5)
        assert config.default_retention_days == 30
        assert config.min_snapshots_to_keep == 20
        assert config.default_commit_strategy == CommitStrategy.MERGE_COMMIT

    @pytest.mark.requirement("FR-045")
    def test_validation_max_commit_retries_min(self) -> None:
        """Test max_commit_retries minimum validation."""
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            IcebergTableManagerConfig(max_commit_retries=0)

    @pytest.mark.requirement("FR-045")
    def test_validation_max_commit_retries_max(self) -> None:
        """Test max_commit_retries maximum validation."""
        with pytest.raises(ValueError, match="less than or equal to 10"):
            IcebergTableManagerConfig(max_commit_retries=11)

    @pytest.mark.requirement("FR-045")
    def test_validation_retry_delay_min(self) -> None:
        """Test retry_base_delay_seconds minimum validation."""
        with pytest.raises(ValueError, match="greater than or equal to 0.1"):
            IcebergTableManagerConfig(retry_base_delay_seconds=0.05)

    @pytest.mark.requirement("FR-045")
    def test_validation_retry_delay_max(self) -> None:
        """Test retry_base_delay_seconds maximum validation."""
        with pytest.raises(ValueError, match="less than or equal to 30"):
            IcebergTableManagerConfig(retry_base_delay_seconds=31.0)

    @pytest.mark.requirement("FR-045")
    def test_validation_retention_days_min(self) -> None:
        """Test default_retention_days minimum validation."""
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            IcebergTableManagerConfig(default_retention_days=0)

    @pytest.mark.requirement("FR-045")
    def test_validation_retention_days_max(self) -> None:
        """Test default_retention_days maximum validation."""
        with pytest.raises(ValueError, match="less than or equal to 365"):
            IcebergTableManagerConfig(default_retention_days=366)

    @pytest.mark.requirement("FR-045")
    def test_validation_min_snapshots_min(self) -> None:
        """Test min_snapshots_to_keep minimum validation."""
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            IcebergTableManagerConfig(min_snapshots_to_keep=0)

    @pytest.mark.requirement("FR-045")
    def test_validation_min_snapshots_max(self) -> None:
        """Test min_snapshots_to_keep maximum validation."""
        with pytest.raises(ValueError, match="less than or equal to 100"):
            IcebergTableManagerConfig(min_snapshots_to_keep=101)

    @pytest.mark.requirement("FR-045")
    def test_frozen(self) -> None:
        """Test config is immutable (frozen)."""
        config = IcebergTableManagerConfig()
        with pytest.raises(Exception):  # ValidationError for frozen models
            config.max_commit_retries = 5  # type: ignore[misc]

    @pytest.mark.requirement("FR-045")
    def test_extra_forbid(self) -> None:
        """Test config rejects extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            IcebergTableManagerConfig(unknown_field="value")  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-045")
    def test_custom_table_properties(self) -> None:
        """Test custom table properties can be set."""
        custom_props = {"write.format.default": "avro", "custom.property": "value"}
        config = IcebergTableManagerConfig(default_table_properties=custom_props)
        assert config.default_table_properties["write.format.default"] == "avro"
        assert config.default_table_properties["custom.property"] == "value"


# =============================================================================
# IcebergIOManagerConfig Tests
# =============================================================================


class TestIcebergIOManagerConfig:
    """Tests for IcebergIOManagerConfig model."""

    @pytest.mark.requirement("FR-037")
    def test_required_namespace(self) -> None:
        """Test namespace is required."""
        with pytest.raises(ValueError, match="Field required"):
            IcebergIOManagerConfig()  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-037")
    def test_minimal_config(self) -> None:
        """Test config with only required fields."""
        config = IcebergIOManagerConfig(namespace="bronze")
        assert config.namespace == "bronze"
        assert config.default_write_mode == WriteMode.APPEND
        assert config.default_commit_strategy == CommitStrategy.FAST_APPEND
        assert config.table_name_pattern == "{asset_key}"
        assert config.infer_schema_from_data is True

    @pytest.mark.requirement("FR-037")
    def test_custom_values(self) -> None:
        """Test config accepts custom values."""
        config = IcebergIOManagerConfig(
            namespace="silver",
            default_write_mode=WriteMode.UPSERT,
            default_commit_strategy=CommitStrategy.MERGE_COMMIT,
            table_name_pattern="dim_{asset_key}",
            infer_schema_from_data=False,
        )
        assert config.namespace == "silver"
        assert config.default_write_mode == WriteMode.UPSERT
        assert config.default_commit_strategy == CommitStrategy.MERGE_COMMIT
        assert config.table_name_pattern == "dim_{asset_key}"
        assert config.infer_schema_from_data is False

    @pytest.mark.requirement("FR-037")
    def test_namespace_validation_pattern(self) -> None:
        """Test namespace must match IDENTIFIER_PATTERN."""
        with pytest.raises(ValueError, match="String should match pattern"):
            IcebergIOManagerConfig(namespace="123invalid")

    @pytest.mark.requirement("FR-037")
    def test_namespace_validation_empty(self) -> None:
        """Test namespace cannot be empty."""
        with pytest.raises(ValueError, match="String should have at least 1 character"):
            IcebergIOManagerConfig(namespace="")

    @pytest.mark.requirement("FR-037")
    def test_namespace_validation_max_length(self) -> None:
        """Test namespace max length."""
        long_name = "a" * 256
        with pytest.raises(ValueError, match="String should have at most 255 characters"):
            IcebergIOManagerConfig(namespace=long_name)

    @pytest.mark.requirement("FR-037")
    def test_frozen(self) -> None:
        """Test config is immutable (frozen)."""
        config = IcebergIOManagerConfig(namespace="test")
        with pytest.raises(Exception):  # ValidationError for frozen models
            config.namespace = "changed"  # type: ignore[misc]

    @pytest.mark.requirement("FR-037")
    def test_extra_forbid(self) -> None:
        """Test config rejects extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            IcebergIOManagerConfig(namespace="test", unknown="value")  # type: ignore[call-arg]
