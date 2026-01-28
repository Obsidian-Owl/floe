"""Unit tests for quality check parsing and dbt test mapping.

Tests cover:
- T040: FloeSpec quality_checks parsing from floe.yaml
- T041: TransformSpec tier and quality_checks fields
- T043-T044a: dbt test to QualityCheck mapping and deduplication
- T045: Column reference validation (FLOE-DQ105)
- T046: Quality checks in ResolvedModel compilation
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.compilation.dbt_test_mapper import (
    DBT_TEST_DIMENSION_MAP,
    DEFAULT_DBT_TEST_SEVERITY,
    deduplicate_checks,
    get_check_signature,
    infer_dimension,
    map_dbt_test_to_check,
    merge_model_checks,
)
from floe_core.schemas.floe_spec import FloeMetadata, FloeSpec, TransformSpec
from floe_core.schemas.quality_config import Dimension, SeverityLevel
from floe_core.schemas.quality_score import QualityCheck
from floe_core.validation.quality_validation import (
    validate_check_column_references,
)


# =============================================================================
# T040-T041: FloeSpec quality_checks parsing
# =============================================================================


class TestTransformSpecQualityFields:
    """Test TransformSpec accepts tier and quality_checks fields."""

    @pytest.mark.requirement("005B-US-002")
    def test_transform_spec_with_tier(self) -> None:
        """Test TransformSpec accepts valid tier values."""
        for tier in ("bronze", "silver", "gold"):
            transform = TransformSpec(name="test_model", tier=tier)
            assert transform.tier == tier

    @pytest.mark.requirement("005B-US-002")
    def test_transform_spec_tier_optional(self) -> None:
        """Test TransformSpec tier is optional and defaults to None."""
        transform = TransformSpec(name="test_model")
        assert transform.tier is None

    @pytest.mark.requirement("005B-US-002")
    def test_transform_spec_tier_invalid_value(self) -> None:
        """Test TransformSpec rejects invalid tier values."""
        with pytest.raises(ValidationError) as exc_info:
            TransformSpec(name="test_model", tier="platinum")
        assert "Input should be 'bronze', 'silver' or 'gold'" in str(exc_info.value)

    @pytest.mark.requirement("005B-US-002")
    def test_transform_spec_with_quality_checks(self) -> None:
        """Test TransformSpec accepts quality_checks list."""
        check = QualityCheck(
            name="not_null_id",
            type="not_null",
            column="id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
        )
        transform = TransformSpec(name="test_model", quality_checks=[check])
        assert transform.quality_checks is not None
        assert len(transform.quality_checks) == 1
        assert transform.quality_checks[0].name == "not_null_id"

    @pytest.mark.requirement("005B-US-002")
    def test_transform_spec_quality_checks_optional(self) -> None:
        """Test TransformSpec quality_checks is optional and defaults to None."""
        transform = TransformSpec(name="test_model")
        assert transform.quality_checks is None

    @pytest.mark.requirement("005B-US-002")
    def test_transform_spec_combined_tier_and_checks(self) -> None:
        """Test TransformSpec accepts both tier and quality_checks."""
        check = QualityCheck(
            name="unique_pk",
            type="unique",
            column="id",
            dimension=Dimension.CONSISTENCY,
            severity=SeverityLevel.CRITICAL,
        )
        transform = TransformSpec(
            name="gold_customers",
            tier="gold",
            quality_checks=[check],
        )
        assert transform.tier == "gold"
        assert transform.quality_checks is not None
        assert len(transform.quality_checks) == 1


class TestFloeSpecQualityParsing:
    """Test FloeSpec parsing with quality fields."""

    @pytest.mark.requirement("005B-US-002")
    def test_floe_spec_with_quality_transforms(self) -> None:
        """Test FloeSpec parses transforms with quality configuration."""
        check = QualityCheck(
            name="not_null_customer_id",
            type="not_null",
            column="customer_id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,
        )
        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(name="test-product", version="1.0.0"),
            transforms=[TransformSpec(name="stg_customers", tier="silver", quality_checks=[check])],
        )
        assert spec.transforms[0].tier == "silver"
        assert spec.transforms[0].quality_checks is not None
        assert len(spec.transforms[0].quality_checks) == 1

    @pytest.mark.requirement("005B-US-002")
    def test_floe_spec_model_validate_with_quality(self) -> None:
        """Test FloeSpec.model_validate with quality configuration dict."""
        data = {
            "apiVersion": "floe.dev/v1",
            "kind": "FloeSpec",
            "metadata": {"name": "test-product", "version": "1.0.0"},
            "transforms": [
                {
                    "name": "gold_revenue",
                    "tier": "gold",
                    "qualityChecks": [
                        {
                            "name": "not_null_amount",
                            "type": "not_null",
                            "column": "amount",
                            "dimension": "completeness",
                            "severity": "critical",
                        }
                    ],
                }
            ],
        }
        spec = FloeSpec.model_validate(data)
        assert spec.transforms[0].tier == "gold"
        assert spec.transforms[0].quality_checks is not None
        assert spec.transforms[0].quality_checks[0].dimension == Dimension.COMPLETENESS


# =============================================================================
# T043-T044a: dbt test mapping and deduplication
# =============================================================================


class TestDbtTestDimensionMap:
    """Test the DBT_TEST_DIMENSION_MAP mapping."""

    @pytest.mark.requirement("005B-FR-018")
    def test_not_null_maps_to_completeness(self) -> None:
        """Test not_null test maps to COMPLETENESS dimension."""
        assert DBT_TEST_DIMENSION_MAP["not_null"] == Dimension.COMPLETENESS

    @pytest.mark.requirement("005B-FR-018")
    def test_unique_maps_to_consistency(self) -> None:
        """Test unique test maps to CONSISTENCY dimension."""
        assert DBT_TEST_DIMENSION_MAP["unique"] == Dimension.CONSISTENCY

    @pytest.mark.requirement("005B-FR-018")
    def test_relationships_maps_to_consistency(self) -> None:
        """Test relationships test maps to CONSISTENCY dimension."""
        assert DBT_TEST_DIMENSION_MAP["relationships"] == Dimension.CONSISTENCY

    @pytest.mark.requirement("005B-FR-018")
    def test_accepted_values_maps_to_validity(self) -> None:
        """Test accepted_values test maps to VALIDITY dimension."""
        assert DBT_TEST_DIMENSION_MAP["accepted_values"] == Dimension.VALIDITY

    @pytest.mark.requirement("005B-FR-018")
    def test_between_tests_map_to_accuracy(self) -> None:
        """Test range/between tests map to ACCURACY dimension."""
        assert DBT_TEST_DIMENSION_MAP["expect_column_values_to_be_between"] == Dimension.ACCURACY
        assert DBT_TEST_DIMENSION_MAP["expect_column_min_to_be_between"] == Dimension.ACCURACY


class TestInferDimension:
    """Test the infer_dimension function."""

    @pytest.mark.requirement("005B-FR-018")
    def test_infer_known_test_type(self) -> None:
        """Test inference for known test types."""
        assert infer_dimension("not_null") == Dimension.COMPLETENESS
        assert infer_dimension("unique") == Dimension.CONSISTENCY
        assert infer_dimension("accepted_values") == Dimension.VALIDITY

    @pytest.mark.requirement("005B-FR-018")
    def test_infer_unknown_test_type_defaults_to_validity(self) -> None:
        """Test unknown test types default to VALIDITY dimension."""
        assert infer_dimension("custom_test") == Dimension.VALIDITY
        assert infer_dimension("unknown_check") == Dimension.VALIDITY


class TestMapDbtTestToCheck:
    """Test the map_dbt_test_to_check function."""

    @pytest.mark.requirement("005B-FR-018")
    def test_map_not_null_test(self) -> None:
        """Test mapping a not_null test to QualityCheck."""
        check = map_dbt_test_to_check(
            model_name="stg_customers",
            test_type="not_null",
            column="customer_id",
        )
        assert check.name == "stg_customers_customer_id_not_null"
        assert check.type == "not_null"
        assert check.column == "customer_id"
        assert check.dimension == Dimension.COMPLETENESS
        assert check.severity == DEFAULT_DBT_TEST_SEVERITY

    @pytest.mark.requirement("005B-FR-018")
    def test_map_unique_test(self) -> None:
        """Test mapping a unique test to QualityCheck."""
        check = map_dbt_test_to_check(
            model_name="dim_products",
            test_type="unique",
            column="product_id",
        )
        assert check.name == "dim_products_product_id_unique"
        assert check.dimension == Dimension.CONSISTENCY

    @pytest.mark.requirement("005B-FR-018")
    def test_map_accepted_values_test_with_parameters(self) -> None:
        """Test mapping accepted_values test with parameters."""
        check = map_dbt_test_to_check(
            model_name="stg_orders",
            test_type="accepted_values",
            column="status",
            parameters={"values": ["pending", "shipped", "delivered"]},
        )
        assert check.name == "stg_orders_status_accepted_values"
        assert check.dimension == Dimension.VALIDITY
        assert check.parameters == {"values": ["pending", "shipped", "delivered"]}

    @pytest.mark.requirement("005B-FR-018")
    def test_map_table_level_test(self) -> None:
        """Test mapping a table-level test (no column)."""
        check = map_dbt_test_to_check(
            model_name="fct_sales",
            test_type="row_count",
            column=None,
        )
        assert check.name == "fct_sales_row_count"
        assert check.column is None

    @pytest.mark.requirement("005B-FR-018")
    def test_map_with_custom_severity(self) -> None:
        """Test mapping with custom severity override."""
        check = map_dbt_test_to_check(
            model_name="gold_metrics",
            test_type="not_null",
            column="revenue",
            severity=SeverityLevel.CRITICAL,
        )
        assert check.severity == SeverityLevel.CRITICAL


class TestGetCheckSignature:
    """Test the get_check_signature function for deduplication."""

    @pytest.mark.requirement("005B-FR-018")
    def test_signature_for_column_check(self) -> None:
        """Test signature generation for column-level check."""
        check = QualityCheck(
            name="test_check",
            type="not_null",
            column="customer_id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        signature = get_check_signature(check)
        assert signature == "not_null:customer_id"

    @pytest.mark.requirement("005B-FR-018")
    def test_signature_for_table_check(self) -> None:
        """Test signature generation for table-level check."""
        check = QualityCheck(
            name="test_check",
            type="row_count",
            column=None,
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.INFO,
        )
        signature = get_check_signature(check)
        assert signature == "row_count:__table__"


class TestDeduplicateChecks:
    """Test the deduplicate_checks function."""

    @pytest.mark.requirement("005B-FR-018")
    def test_dbt_checks_take_precedence(self) -> None:
        """Test that dbt checks take precedence over floe checks."""
        dbt_check = QualityCheck(
            name="dbt_not_null_id",
            type="not_null",
            column="id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        floe_check = QualityCheck(
            name="floe_not_null_id",
            type="not_null",
            column="id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.CRITICAL,  # Different severity
        )
        result = deduplicate_checks([dbt_check], [floe_check])
        assert len(result) == 1
        assert result[0].name == "dbt_not_null_id"  # dbt wins
        assert result[0].severity == SeverityLevel.WARNING

    @pytest.mark.requirement("005B-FR-018")
    def test_non_duplicate_checks_preserved(self) -> None:
        """Test that non-duplicate floe checks are preserved."""
        dbt_check = QualityCheck(
            name="dbt_not_null_id",
            type="not_null",
            column="id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        floe_check = QualityCheck(
            name="floe_unique_email",
            type="unique",
            column="email",
            dimension=Dimension.CONSISTENCY,
            severity=SeverityLevel.CRITICAL,
        )
        result = deduplicate_checks([dbt_check], [floe_check])
        assert len(result) == 2
        assert result[0].name == "dbt_not_null_id"  # dbt first
        assert result[1].name == "floe_unique_email"  # floe second

    @pytest.mark.requirement("005B-FR-018")
    def test_empty_dbt_checks(self) -> None:
        """Test with no dbt checks."""
        floe_check = QualityCheck(
            name="floe_check",
            type="not_null",
            column="id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        result = deduplicate_checks([], [floe_check])
        assert len(result) == 1
        assert result[0].name == "floe_check"

    @pytest.mark.requirement("005B-FR-018")
    def test_empty_floe_checks(self) -> None:
        """Test with no floe checks."""
        dbt_check = QualityCheck(
            name="dbt_check",
            type="not_null",
            column="id",
            dimension=Dimension.COMPLETENESS,
            severity=SeverityLevel.WARNING,
        )
        result = deduplicate_checks([dbt_check], [])
        assert len(result) == 1
        assert result[0].name == "dbt_check"


class TestMergeModelChecks:
    """Test the merge_model_checks function."""

    @pytest.mark.requirement("005B-FR-018")
    def test_merge_dbt_tests_only(self) -> None:
        """Test merging with only dbt tests."""
        dbt_tests = [
            {"type": "not_null", "column": "id"},
            {"type": "unique", "column": "id"},
        ]
        result = merge_model_checks("test_model", dbt_tests, None)
        assert len(result) == 2
        assert result[0].name == "test_model_id_not_null"
        assert result[1].name == "test_model_id_unique"

    @pytest.mark.requirement("005B-FR-018")
    def test_merge_floe_checks_only(self) -> None:
        """Test merging with only floe checks."""
        floe_checks = [
            QualityCheck(
                name="custom_check",
                type="custom",
                column="value",
                dimension=Dimension.ACCURACY,
                severity=SeverityLevel.WARNING,
            )
        ]
        result = merge_model_checks("test_model", [], floe_checks)
        assert len(result) == 1
        assert result[0].name == "custom_check"

    @pytest.mark.requirement("005B-FR-018")
    def test_merge_with_deduplication(self) -> None:
        """Test merging with deduplication (dbt wins)."""
        dbt_tests = [{"type": "not_null", "column": "id"}]
        floe_checks = [
            QualityCheck(
                name="floe_not_null_id",
                type="not_null",
                column="id",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.CRITICAL,
            )
        ]
        result = merge_model_checks("test_model", dbt_tests, floe_checks)
        assert len(result) == 1
        assert result[0].name == "test_model_id_not_null"  # dbt version wins

    @pytest.mark.requirement("005B-FR-018")
    def test_merge_with_test_key_instead_of_type(self) -> None:
        """Test that 'test' key works as alias for 'type'."""
        dbt_tests = [{"test": "not_null", "column": "id"}]
        result = merge_model_checks("test_model", dbt_tests, None)
        assert len(result) == 1
        assert result[0].type == "not_null"


# =============================================================================
# T045: Column reference validation (FLOE-DQ105)
# =============================================================================


class TestColumnReferenceValidation:
    """Test column reference validation for FLOE-DQ105."""

    @pytest.mark.requirement("005B-FLOE-DQ105")
    def test_valid_column_references(self) -> None:
        """Test validation passes for valid column references."""
        checks = [
            QualityCheck(
                name="not_null_id",
                type="not_null",
                column="id",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
            QualityCheck(
                name="not_null_name",
                type="not_null",
                column="name",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
        ]
        available_columns = ["id", "name", "email"]
        # Should not raise
        validate_check_column_references("test_model", checks, available_columns)

    @pytest.mark.requirement("005B-FLOE-DQ105")
    def test_invalid_column_reference_raises(self) -> None:
        """Test validation raises FLOE-DQ105 for invalid column reference."""
        from floe_core.quality_errors import QualityColumnReferenceError

        checks = [
            QualityCheck(
                name="not_null_invalid",
                type="not_null",
                column="nonexistent_column",
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            )
        ]
        available_columns = ["id", "name", "email"]
        with pytest.raises(QualityColumnReferenceError) as exc_info:
            validate_check_column_references("test_model", checks, available_columns)
        assert exc_info.value.error_code == "FLOE-DQ105"
        assert "nonexistent_column" in str(exc_info.value)

    @pytest.mark.requirement("005B-FLOE-DQ105")
    def test_table_level_check_no_column_validation(self) -> None:
        """Test table-level checks (column=None) skip column validation."""
        checks = [
            QualityCheck(
                name="row_count_check",
                type="row_count",
                column=None,  # Table-level check
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.INFO,
            )
        ]
        available_columns = ["id", "name"]
        # Should not raise for table-level check
        validate_check_column_references("test_model", checks, available_columns)

    @pytest.mark.requirement("005B-FLOE-DQ105")
    def test_empty_checks_list(self) -> None:
        """Test validation passes for empty checks list."""
        available_columns = ["id", "name"]
        # Should not raise
        validate_check_column_references("test_model", [], available_columns)

    @pytest.mark.requirement("005B-FLOE-DQ105")
    def test_validation_skipped_when_no_columns(self) -> None:
        """Test validation is skipped when available_columns is None."""
        checks = [
            QualityCheck(
                name="check1",
                type="not_null",
                column="any_column",  # Would be invalid if columns were provided
                dimension=Dimension.COMPLETENESS,
                severity=SeverityLevel.WARNING,
            ),
        ]
        # Should not raise when available_columns is None
        validate_check_column_references("test_model", checks, None)
