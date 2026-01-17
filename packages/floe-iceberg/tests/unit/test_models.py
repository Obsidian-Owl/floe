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
    SchemaChange,
    SchemaChangeType,
    SchemaEvolution,
    SchemaField,
    SnapshotInfo,
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


# =============================================================================
# SchemaField Tests
# =============================================================================


class TestSchemaField:
    """Tests for SchemaField model."""

    @pytest.mark.requirement("FR-012")
    def test_minimal_field(self) -> None:
        """Test SchemaField with minimal required fields."""
        from floe_iceberg.models import SchemaField

        field = SchemaField(
            field_id=1,
            name="customer_id",
            field_type=FieldType.LONG,
        )
        assert field.field_id == 1
        assert field.name == "customer_id"
        assert field.field_type == FieldType.LONG
        assert field.required is False
        assert field.doc is None

    @pytest.mark.requirement("FR-012")
    def test_field_with_all_attributes(self) -> None:
        """Test SchemaField with all attributes."""
        from floe_iceberg.models import SchemaField

        field = SchemaField(
            field_id=1,
            name="customer_id",
            field_type=FieldType.LONG,
            required=True,
            doc="Primary customer identifier",
        )
        assert field.required is True
        assert field.doc == "Primary customer identifier"

    @pytest.mark.requirement("FR-012")
    def test_decimal_field_with_precision_scale(self) -> None:
        """Test SchemaField for decimal type with precision/scale."""
        from floe_iceberg.models import SchemaField

        field = SchemaField(
            field_id=1,
            name="amount",
            field_type=FieldType.DECIMAL,
            precision=10,
            scale=2,
        )
        assert field.precision == 10
        assert field.scale == 2

    @pytest.mark.requirement("FR-012")
    def test_field_id_validation_positive(self) -> None:
        """Test field_id must be positive."""
        from floe_iceberg.models import SchemaField

        with pytest.raises(ValueError, match="greater than or equal to 1"):
            SchemaField(
                field_id=0,
                name="test",
                field_type=FieldType.STRING,
            )

    @pytest.mark.requirement("FR-012")
    def test_name_pattern_validation(self) -> None:
        """Test name must match IDENTIFIER_PATTERN."""
        from floe_iceberg.models import SchemaField

        with pytest.raises(ValueError, match="String should match pattern"):
            SchemaField(
                field_id=1,
                name="123invalid",
                field_type=FieldType.STRING,
            )

    @pytest.mark.requirement("FR-012")
    def test_name_empty_validation(self) -> None:
        """Test name cannot be empty."""
        from floe_iceberg.models import SchemaField

        with pytest.raises(ValueError, match="String should have at least 1 character"):
            SchemaField(
                field_id=1,
                name="",
                field_type=FieldType.STRING,
            )

    @pytest.mark.requirement("FR-012")
    def test_precision_range_validation(self) -> None:
        """Test precision must be 1-38."""
        from floe_iceberg.models import SchemaField

        with pytest.raises(ValueError, match="less than or equal to 38"):
            SchemaField(
                field_id=1,
                name="amount",
                field_type=FieldType.DECIMAL,
                precision=39,
            )

    @pytest.mark.requirement("FR-012")
    def test_scale_non_negative_validation(self) -> None:
        """Test scale must be non-negative."""
        from floe_iceberg.models import SchemaField

        with pytest.raises(ValueError, match="greater than or equal to 0"):
            SchemaField(
                field_id=1,
                name="amount",
                field_type=FieldType.DECIMAL,
                scale=-1,
            )

    @pytest.mark.requirement("FR-012")
    def test_frozen(self) -> None:
        """Test SchemaField is immutable."""
        from floe_iceberg.models import SchemaField

        field = SchemaField(
            field_id=1,
            name="test",
            field_type=FieldType.STRING,
        )
        with pytest.raises(Exception):
            field.name = "changed"  # type: ignore[misc]

    @pytest.mark.requirement("FR-012")
    def test_extra_forbid(self) -> None:
        """Test SchemaField rejects extra fields."""
        from floe_iceberg.models import SchemaField

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            SchemaField(
                field_id=1,
                name="test",
                field_type=FieldType.STRING,
                unknown="value",  # type: ignore[call-arg]
            )


# =============================================================================
# TableSchema Tests
# =============================================================================


class TestTableSchema:
    """Tests for TableSchema model."""

    @pytest.mark.requirement("FR-012")
    def test_minimal_schema(self) -> None:
        """Test TableSchema with single field."""
        from floe_iceberg.models import SchemaField, TableSchema

        schema = TableSchema(
            fields=[
                SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
            ]
        )
        assert len(schema.fields) == 1

    @pytest.mark.requirement("FR-012")
    def test_multi_field_schema(self) -> None:
        """Test TableSchema with multiple fields."""
        from floe_iceberg.models import SchemaField, TableSchema

        schema = TableSchema(
            fields=[
                SchemaField(field_id=1, name="id", field_type=FieldType.LONG, required=True),
                SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
                SchemaField(field_id=3, name="created_at", field_type=FieldType.TIMESTAMPTZ),
            ]
        )
        assert len(schema.fields) == 3
        assert schema.fields[0].required is True
        assert schema.fields[1].name == "name"

    @pytest.mark.requirement("FR-012")
    def test_empty_fields_validation(self) -> None:
        """Test TableSchema requires at least one field."""
        from floe_iceberg.models import TableSchema

        with pytest.raises(ValueError, match="List should have at least 1 item"):
            TableSchema(fields=[])

    @pytest.mark.requirement("FR-012")
    def test_frozen(self) -> None:
        """Test TableSchema is immutable."""
        from floe_iceberg.models import SchemaField, TableSchema

        schema = TableSchema(
            fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
        )
        with pytest.raises(Exception):
            schema.fields = []  # type: ignore[misc]


# =============================================================================
# PartitionField Tests
# =============================================================================


class TestPartitionField:
    """Tests for PartitionField model."""

    @pytest.mark.requirement("FR-014")
    def test_minimal_partition_field(self) -> None:
        """Test PartitionField with minimal fields."""
        from floe_iceberg.models import PartitionField

        field = PartitionField(
            source_field_id=1,
            partition_field_id=1000,
            name="date_day",
            transform=PartitionTransform.DAY,
        )
        assert field.source_field_id == 1
        assert field.partition_field_id == 1000
        assert field.name == "date_day"
        assert field.transform == PartitionTransform.DAY

    @pytest.mark.requirement("FR-014")
    def test_bucket_partition_field(self) -> None:
        """Test PartitionField with bucket transform."""
        from floe_iceberg.models import PartitionField

        field = PartitionField(
            source_field_id=1,
            partition_field_id=1000,
            name="id_bucket",
            transform=PartitionTransform.BUCKET,
            num_buckets=16,
        )
        assert field.transform == PartitionTransform.BUCKET
        assert field.num_buckets == 16

    @pytest.mark.requirement("FR-014")
    def test_truncate_partition_field(self) -> None:
        """Test PartitionField with truncate transform."""
        from floe_iceberg.models import PartitionField

        field = PartitionField(
            source_field_id=1,
            partition_field_id=1000,
            name="str_truncate",
            transform=PartitionTransform.TRUNCATE,
            width=10,
        )
        assert field.transform == PartitionTransform.TRUNCATE
        assert field.width == 10

    @pytest.mark.requirement("FR-014")
    def test_partition_field_id_min_validation(self) -> None:
        """Test partition_field_id must be >= 1000."""
        from floe_iceberg.models import PartitionField

        with pytest.raises(ValueError, match="greater than or equal to 1000"):
            PartitionField(
                source_field_id=1,
                partition_field_id=999,
                name="test",
                transform=PartitionTransform.IDENTITY,
            )

    @pytest.mark.requirement("FR-014")
    def test_source_field_id_positive_validation(self) -> None:
        """Test source_field_id must be positive."""
        from floe_iceberg.models import PartitionField

        with pytest.raises(ValueError, match="greater than or equal to 1"):
            PartitionField(
                source_field_id=0,
                partition_field_id=1000,
                name="test",
                transform=PartitionTransform.IDENTITY,
            )

    @pytest.mark.requirement("FR-014")
    def test_frozen(self) -> None:
        """Test PartitionField is immutable."""
        from floe_iceberg.models import PartitionField

        field = PartitionField(
            source_field_id=1,
            partition_field_id=1000,
            name="test",
            transform=PartitionTransform.IDENTITY,
        )
        with pytest.raises(Exception):
            field.name = "changed"  # type: ignore[misc]


# =============================================================================
# PartitionSpec Tests
# =============================================================================


class TestPartitionSpec:
    """Tests for PartitionSpec model."""

    @pytest.mark.requirement("FR-014")
    def test_empty_partition_spec(self) -> None:
        """Test PartitionSpec can be empty (unpartitioned)."""
        from floe_iceberg.models import PartitionSpec

        spec = PartitionSpec()
        assert len(spec.fields) == 0

    @pytest.mark.requirement("FR-014")
    def test_single_partition_field(self) -> None:
        """Test PartitionSpec with single field."""
        from floe_iceberg.models import PartitionField, PartitionSpec

        spec = PartitionSpec(
            fields=[
                PartitionField(
                    source_field_id=1,
                    partition_field_id=1000,
                    name="date_day",
                    transform=PartitionTransform.DAY,
                )
            ]
        )
        assert len(spec.fields) == 1

    @pytest.mark.requirement("FR-014")
    def test_multiple_partition_fields(self) -> None:
        """Test PartitionSpec with multiple fields."""
        from floe_iceberg.models import PartitionField, PartitionSpec

        spec = PartitionSpec(
            fields=[
                PartitionField(
                    source_field_id=1,
                    partition_field_id=1000,
                    name="date_day",
                    transform=PartitionTransform.DAY,
                ),
                PartitionField(
                    source_field_id=2,
                    partition_field_id=1001,
                    name="region_bucket",
                    transform=PartitionTransform.BUCKET,
                    num_buckets=8,
                ),
            ]
        )
        assert len(spec.fields) == 2

    @pytest.mark.requirement("FR-014")
    def test_frozen(self) -> None:
        """Test PartitionSpec is immutable."""
        from floe_iceberg.models import PartitionSpec

        spec = PartitionSpec()
        with pytest.raises(Exception):
            spec.fields = []  # type: ignore[misc]


# =============================================================================
# TableConfig Tests
# =============================================================================


class TestTableConfig:
    """Tests for TableConfig model."""

    @pytest.mark.requirement("FR-013")
    def test_minimal_config(self) -> None:
        """Test TableConfig with minimal fields."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        config = TableConfig(
            namespace="bronze",
            table_name="customers",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        assert config.namespace == "bronze"
        assert config.table_name == "customers"
        assert config.partition_spec is None
        assert config.location is None
        assert config.properties == {}

    @pytest.mark.requirement("FR-013")
    def test_identifier_property(self) -> None:
        """Test identifier property returns full table name."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        config = TableConfig(
            namespace="bronze",
            table_name="customers",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        assert config.identifier == "bronze.customers"

    @pytest.mark.requirement("FR-013")
    def test_config_with_partition(self) -> None:
        """Test TableConfig with partition specification."""
        from floe_iceberg.models import (
            PartitionField,
            PartitionSpec,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        config = TableConfig(
            namespace="silver",
            table_name="orders",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="order_date", field_type=FieldType.DATE),
                ]
            ),
            partition_spec=PartitionSpec(
                fields=[
                    PartitionField(
                        source_field_id=2,
                        partition_field_id=1000,
                        name="order_date_day",
                        transform=PartitionTransform.DAY,
                    )
                ]
            ),
        )
        assert config.partition_spec is not None
        assert len(config.partition_spec.fields) == 1

    @pytest.mark.requirement("FR-013")
    def test_config_with_location(self) -> None:
        """Test TableConfig with custom location."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        config = TableConfig(
            namespace="bronze",
            table_name="customers",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
            location="s3://my-bucket/bronze/customers",
        )
        assert config.location == "s3://my-bucket/bronze/customers"

    @pytest.mark.requirement("FR-013")
    def test_config_with_properties(self) -> None:
        """Test TableConfig with custom properties."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        config = TableConfig(
            namespace="bronze",
            table_name="customers",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
            properties={"write.format.default": "avro"},
        )
        assert config.properties["write.format.default"] == "avro"

    @pytest.mark.requirement("FR-013")
    def test_namespace_pattern_validation(self) -> None:
        """Test namespace must match IDENTIFIER_PATTERN."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        with pytest.raises(ValueError, match="String should match pattern"):
            TableConfig(
                namespace="123invalid",
                table_name="customers",
                table_schema=TableSchema(
                    fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
                ),
            )

    @pytest.mark.requirement("FR-013")
    def test_table_name_pattern_validation(self) -> None:
        """Test table_name must match IDENTIFIER_PATTERN."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        with pytest.raises(ValueError, match="String should match pattern"):
            TableConfig(
                namespace="bronze",
                table_name="_invalid",
                table_schema=TableSchema(
                    fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
                ),
            )

    @pytest.mark.requirement("FR-013")
    def test_frozen(self) -> None:
        """Test TableConfig is immutable."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        config = TableConfig(
            namespace="bronze",
            table_name="customers",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        with pytest.raises(Exception):
            config.namespace = "changed"  # type: ignore[misc]

    @pytest.mark.requirement("FR-013")
    def test_extra_forbid(self) -> None:
        """Test TableConfig rejects extra fields."""
        from floe_iceberg.models import SchemaField, TableConfig, TableSchema

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            TableConfig(
                namespace="bronze",
                table_name="customers",
                table_schema=TableSchema(
                    fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
                ),
                unknown="value",  # type: ignore[call-arg]
            )


# =============================================================================
# SchemaChange Tests
# =============================================================================


class TestSchemaChange:
    """Tests for SchemaChange model."""

    @pytest.mark.requirement("FR-017")
    def test_add_column_change(self) -> None:
        """Test SchemaChange for ADD_COLUMN operation."""
        change = SchemaChange(
            change_type=SchemaChangeType.ADD_COLUMN,
            field=SchemaField(field_id=10, name="email", field_type=FieldType.STRING),
        )
        assert change.change_type == SchemaChangeType.ADD_COLUMN
        assert change.field is not None
        assert change.field.name == "email"

    @pytest.mark.requirement("FR-017")
    def test_add_column_with_parent_path(self) -> None:
        """Test ADD_COLUMN with nested parent path."""
        change = SchemaChange(
            change_type=SchemaChangeType.ADD_COLUMN,
            field=SchemaField(field_id=10, name="street", field_type=FieldType.STRING),
            parent_path=("address",),
        )
        assert change.parent_path == ("address",)

    @pytest.mark.requirement("FR-018")
    def test_rename_column_change(self) -> None:
        """Test SchemaChange for RENAME_COLUMN operation."""
        change = SchemaChange(
            change_type=SchemaChangeType.RENAME_COLUMN,
            source_column="old_name",
            new_name="new_name",
        )
        assert change.change_type == SchemaChangeType.RENAME_COLUMN
        assert change.source_column == "old_name"
        assert change.new_name == "new_name"

    @pytest.mark.requirement("FR-019")
    def test_widen_type_change(self) -> None:
        """Test SchemaChange for WIDEN_TYPE operation."""
        change = SchemaChange(
            change_type=SchemaChangeType.WIDEN_TYPE,
            source_column="amount",
            target_type=FieldType.DOUBLE,
        )
        assert change.change_type == SchemaChangeType.WIDEN_TYPE
        assert change.source_column == "amount"
        assert change.target_type == FieldType.DOUBLE

    @pytest.mark.requirement("FR-020")
    def test_make_optional_change(self) -> None:
        """Test SchemaChange for MAKE_OPTIONAL operation."""
        change = SchemaChange(
            change_type=SchemaChangeType.MAKE_OPTIONAL,
            source_column="required_field",
        )
        assert change.change_type == SchemaChangeType.MAKE_OPTIONAL
        assert change.source_column == "required_field"

    @pytest.mark.requirement("FR-020")
    def test_delete_column_change(self) -> None:
        """Test SchemaChange for DELETE_COLUMN operation (incompatible)."""
        change = SchemaChange(
            change_type=SchemaChangeType.DELETE_COLUMN,
            source_column="deprecated_field",
        )
        assert change.change_type == SchemaChangeType.DELETE_COLUMN
        assert change.source_column == "deprecated_field"

    @pytest.mark.requirement("FR-021")
    def test_update_doc_change(self) -> None:
        """Test SchemaChange for UPDATE_DOC operation."""
        change = SchemaChange(
            change_type=SchemaChangeType.UPDATE_DOC,
            source_column="customer_id",
            new_doc="Unique customer identifier from CRM system",
        )
        assert change.change_type == SchemaChangeType.UPDATE_DOC
        assert change.source_column == "customer_id"
        assert change.new_doc == "Unique customer identifier from CRM system"

    @pytest.mark.requirement("FR-017")
    def test_change_type_required(self) -> None:
        """Test change_type is required."""
        with pytest.raises(ValueError, match="Field required"):
            SchemaChange()  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-017")
    def test_default_values_are_none(self) -> None:
        """Test all optional fields default to None."""
        change = SchemaChange(change_type=SchemaChangeType.MAKE_OPTIONAL)
        assert change.field is None
        assert change.parent_path is None
        assert change.source_column is None
        assert change.new_name is None
        assert change.target_type is None
        assert change.target_column is None
        assert change.new_doc is None

    @pytest.mark.requirement("FR-017")
    def test_frozen(self) -> None:
        """Test SchemaChange is immutable."""
        change = SchemaChange(
            change_type=SchemaChangeType.ADD_COLUMN,
            field=SchemaField(field_id=10, name="test", field_type=FieldType.STRING),
        )
        with pytest.raises(Exception):
            change.change_type = SchemaChangeType.DELETE_COLUMN  # type: ignore[misc]

    @pytest.mark.requirement("FR-017")
    def test_extra_forbid(self) -> None:
        """Test SchemaChange rejects extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            SchemaChange(
                change_type=SchemaChangeType.ADD_COLUMN,
                unknown="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-017")
    def test_change_with_target_column(self) -> None:
        """Test SchemaChange with target_column for column operations."""
        change = SchemaChange(
            change_type=SchemaChangeType.RENAME_COLUMN,
            source_column="old_name",
            target_column="target_table.column",
            new_name="new_name",
        )
        assert change.target_column == "target_table.column"


# =============================================================================
# SchemaEvolution Tests
# =============================================================================


class TestSchemaEvolution:
    """Tests for SchemaEvolution model."""

    @pytest.mark.requirement("FR-017")
    def test_single_change(self) -> None:
        """Test SchemaEvolution with single change."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=10, name="email", field_type=FieldType.STRING),
                )
            ]
        )
        assert len(evolution.changes) == 1
        assert evolution.allow_incompatible_changes is False

    @pytest.mark.requirement("FR-017")
    def test_multiple_changes(self) -> None:
        """Test SchemaEvolution with multiple changes."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=10, name="email", field_type=FieldType.STRING),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="old_name",
                    new_name="new_name",
                ),
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="amount",
                    target_type=FieldType.DOUBLE,
                ),
            ]
        )
        assert len(evolution.changes) == 3
        assert evolution.changes[0].change_type == SchemaChangeType.ADD_COLUMN
        assert evolution.changes[1].change_type == SchemaChangeType.RENAME_COLUMN
        assert evolution.changes[2].change_type == SchemaChangeType.WIDEN_TYPE

    @pytest.mark.requirement("FR-020")
    def test_allow_incompatible_changes_false_default(self) -> None:
        """Test allow_incompatible_changes defaults to False."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=10, name="test", field_type=FieldType.STRING),
                )
            ]
        )
        assert evolution.allow_incompatible_changes is False

    @pytest.mark.requirement("FR-020")
    def test_allow_incompatible_changes_true(self) -> None:
        """Test SchemaEvolution with allow_incompatible_changes=True."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="deprecated_field",
                )
            ],
            allow_incompatible_changes=True,
        )
        assert evolution.allow_incompatible_changes is True

    @pytest.mark.requirement("FR-020")
    def test_incompatible_change_with_flag(self) -> None:
        """Test DELETE_COLUMN is valid when allow_incompatible_changes=True."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=10, name="new_field", field_type=FieldType.STRING),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="old_field",
                ),
            ],
            allow_incompatible_changes=True,
        )
        assert len(evolution.changes) == 2
        assert evolution.changes[1].change_type == SchemaChangeType.DELETE_COLUMN

    @pytest.mark.requirement("FR-017")
    def test_changes_required(self) -> None:
        """Test changes list is required."""
        with pytest.raises(ValueError, match="Field required"):
            SchemaEvolution()  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-017")
    def test_changes_min_length(self) -> None:
        """Test changes list must have at least one change."""
        with pytest.raises(ValueError, match="List should have at least 1 item"):
            SchemaEvolution(changes=[])

    @pytest.mark.requirement("FR-017")
    def test_frozen(self) -> None:
        """Test SchemaEvolution is immutable."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=10, name="test", field_type=FieldType.STRING),
                )
            ]
        )
        with pytest.raises(Exception):
            evolution.allow_incompatible_changes = True  # type: ignore[misc]

    @pytest.mark.requirement("FR-017")
    def test_extra_forbid(self) -> None:
        """Test SchemaEvolution rejects extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            SchemaEvolution(
                changes=[
                    SchemaChange(
                        change_type=SchemaChangeType.ADD_COLUMN,
                        field=SchemaField(field_id=10, name="test", field_type=FieldType.STRING),
                    )
                ],
                unknown="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-021")
    def test_mixed_compatible_changes(self) -> None:
        """Test evolution with all compatible change types."""
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=10, name="email", field_type=FieldType.STRING),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="old_name",
                    new_name="new_name",
                ),
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="int_field",
                    target_type=FieldType.LONG,
                ),
                SchemaChange(
                    change_type=SchemaChangeType.MAKE_OPTIONAL,
                    source_column="required_field",
                ),
                SchemaChange(
                    change_type=SchemaChangeType.UPDATE_DOC,
                    source_column="customer_id",
                    new_doc="Updated documentation",
                ),
            ],
            allow_incompatible_changes=False,
        )
        assert len(evolution.changes) == 5
        change_types = [c.change_type for c in evolution.changes]
        assert SchemaChangeType.ADD_COLUMN in change_types
        assert SchemaChangeType.RENAME_COLUMN in change_types
        assert SchemaChangeType.WIDEN_TYPE in change_types
        assert SchemaChangeType.MAKE_OPTIONAL in change_types
        assert SchemaChangeType.UPDATE_DOC in change_types


# =============================================================================
# SnapshotInfo Tests
# =============================================================================


class TestSnapshotInfo:
    """Tests for SnapshotInfo model."""

    @pytest.mark.requirement("FR-003")
    def test_minimal_snapshot_info(self) -> None:
        """Test SnapshotInfo creation with minimal fields."""
        info = SnapshotInfo(
            snapshot_id=1234567890,
            timestamp_ms=1705500000000,
            operation=OperationType.APPEND,
        )
        assert info.snapshot_id == 1234567890
        assert info.timestamp_ms == 1705500000000
        assert info.operation == OperationType.APPEND
        assert info.summary == {}
        assert info.parent_id is None

    @pytest.mark.requirement("FR-006")
    def test_snapshot_info_with_all_fields(self) -> None:
        """Test SnapshotInfo creation with all fields."""
        summary = {
            "added-files-count": "5",
            "added-records-count": "1000",
            "added-data-files": "5",
        }
        info = SnapshotInfo(
            snapshot_id=1234567890,
            timestamp_ms=1705500000000,
            operation=OperationType.OVERWRITE,
            summary=summary,
            parent_id=1234567889,
        )
        assert info.snapshot_id == 1234567890
        assert info.operation == OperationType.OVERWRITE
        assert info.summary == summary
        assert info.parent_id == 1234567889

    @pytest.mark.requirement("FR-022")
    def test_added_files_property(self) -> None:
        """Test added_files computed property from summary."""
        info = SnapshotInfo(
            snapshot_id=123,
            timestamp_ms=1705500000000,
            operation=OperationType.APPEND,
            summary={"added-files-count": "10"},
        )
        assert info.added_files == 10

    @pytest.mark.requirement("FR-022")
    def test_added_files_property_default(self) -> None:
        """Test added_files returns 0 when not in summary."""
        info = SnapshotInfo(
            snapshot_id=123,
            timestamp_ms=1705500000000,
            operation=OperationType.APPEND,
        )
        assert info.added_files == 0

    @pytest.mark.requirement("FR-022")
    def test_added_records_property(self) -> None:
        """Test added_records computed property from summary."""
        info = SnapshotInfo(
            snapshot_id=123,
            timestamp_ms=1705500000000,
            operation=OperationType.APPEND,
            summary={"added-records-count": "5000"},
        )
        assert info.added_records == 5000

    @pytest.mark.requirement("FR-022")
    def test_added_records_property_default(self) -> None:
        """Test added_records returns 0 when not in summary."""
        info = SnapshotInfo(
            snapshot_id=123,
            timestamp_ms=1705500000000,
            operation=OperationType.APPEND,
        )
        assert info.added_records == 0

    @pytest.mark.requirement("FR-006")
    def test_all_operation_types(self) -> None:
        """Test SnapshotInfo with all operation types."""
        for op_type in OperationType:
            info = SnapshotInfo(
                snapshot_id=123,
                timestamp_ms=1705500000000,
                operation=op_type,
            )
            assert info.operation == op_type

    @pytest.mark.requirement("FR-003")
    def test_frozen(self) -> None:
        """Test SnapshotInfo is immutable."""
        info = SnapshotInfo(
            snapshot_id=123,
            timestamp_ms=1705500000000,
            operation=OperationType.APPEND,
        )
        with pytest.raises(Exception):
            info.snapshot_id = 456  # type: ignore[misc]

    @pytest.mark.requirement("FR-003")
    def test_extra_forbid(self) -> None:
        """Test SnapshotInfo rejects extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            SnapshotInfo(
                snapshot_id=123,
                timestamp_ms=1705500000000,
                operation=OperationType.APPEND,
                unknown="value",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-022")
    def test_timestamp_non_negative(self) -> None:
        """Test timestamp_ms must be non-negative."""
        with pytest.raises(ValueError):
            SnapshotInfo(
                snapshot_id=123,
                timestamp_ms=-1,
                operation=OperationType.APPEND,
            )

    @pytest.mark.requirement("FR-003")
    def test_required_fields(self) -> None:
        """Test required fields are enforced."""
        with pytest.raises(ValueError, match="Field required"):
            SnapshotInfo(  # type: ignore[call-arg]
                snapshot_id=123,
                # Missing timestamp_ms and operation
            )
