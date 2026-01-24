"""Unit tests for DataContract Pydantic models.

Task: T014
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-005 (Type Validation), FR-006 (Schema Completeness),
              FR-007 (SLA Duration), FR-008 (Classification),
              FR-009 (Format Constraints), FR-010 (Error Codes)

Note: ODCS re-exports (DataContract, SchemaObject, SchemaProperty) are tested
in tests/contract/test_data_contract_schema.py. This file tests:
1. Type constant classes (ElementType, ElementFormat, Classification, ContractStatus)
2. Floe-specific validation models (ContractViolation, ContractValidationResult, etc.)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from floe_core.schemas.data_contract import (
    Classification,
    ContractStatus,
    ContractValidationResult,
    ContractViolation,
    ElementFormat,
    ElementType,
    SchemaComparisonResult,
    TypeMismatch,
)


class TestContractStatus:
    """Tests for ContractStatus string constants."""

    @pytest.mark.requirement("3C-FR-001")
    def test_valid_status_values(self) -> None:
        """Test all ContractStatus constant values."""
        assert ContractStatus.ACTIVE == "active"
        assert ContractStatus.DEPRECATED == "deprecated"
        assert ContractStatus.SUNSET == "sunset"
        assert ContractStatus.RETIRED == "retired"
        assert ContractStatus.DRAFT == "draft"

    @pytest.mark.requirement("3C-FR-001")
    def test_status_all_values(self) -> None:
        """Test ContractStatus has expected constants."""
        expected = {"active", "deprecated", "sunset", "retired", "draft"}
        actual = {
            ContractStatus.ACTIVE,
            ContractStatus.DEPRECATED,
            ContractStatus.SUNSET,
            ContractStatus.RETIRED,
            ContractStatus.DRAFT,
        }
        assert actual == expected


class TestElementType:
    """Tests for ElementType string constants (FR-005)."""

    @pytest.mark.requirement("3C-FR-005")
    def test_odcs_v31_core_types(self) -> None:
        """Test ODCS v3.1 core logicalType values."""
        # Core ODCS v3.1 types
        assert ElementType.STRING == "string"
        assert ElementType.INTEGER == "integer"
        assert ElementType.NUMBER == "number"
        assert ElementType.BOOLEAN == "boolean"
        assert ElementType.DATE == "date"
        assert ElementType.TIMESTAMP == "timestamp"
        assert ElementType.TIME == "time"
        assert ElementType.ARRAY == "array"
        assert ElementType.OBJECT == "object"

    @pytest.mark.requirement("3C-FR-005")
    def test_backward_compat_aliases(self) -> None:
        """Test backward compatibility type aliases."""
        # These map to ODCS core types
        assert ElementType.INT == "integer"
        assert ElementType.LONG == "integer"
        assert ElementType.FLOAT == "number"
        assert ElementType.DOUBLE == "number"
        assert ElementType.DECIMAL == "number"


class TestElementFormat:
    """Tests for ElementFormat string constants (FR-009)."""

    @pytest.mark.requirement("3C-FR-009")
    def test_format_constraint_values(self) -> None:
        """Test format constraint constant values."""
        assert ElementFormat.EMAIL == "email"
        assert ElementFormat.URI == "uri"
        assert ElementFormat.UUID == "uuid"
        assert ElementFormat.PHONE == "phone"
        assert ElementFormat.DATE == "date"
        assert ElementFormat.DATETIME == "date-time"
        assert ElementFormat.IPV4 == "ipv4"
        assert ElementFormat.IPV6 == "ipv6"


class TestClassification:
    """Tests for Classification string constants (FR-008)."""

    @pytest.mark.requirement("3C-FR-008")
    def test_classification_values(self) -> None:
        """Test classification constant values."""
        assert Classification.PUBLIC == "public"
        assert Classification.INTERNAL == "internal"
        assert Classification.CONFIDENTIAL == "confidential"
        assert Classification.PII == "pii"
        assert Classification.PHI == "phi"
        assert Classification.SENSITIVE == "sensitive"
        assert Classification.RESTRICTED == "restricted"


class TestTypeMismatch:
    """Tests for TypeMismatch model (drift detection)."""

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch_creation(self) -> None:
        """Test TypeMismatch for drift detection."""
        mismatch = TypeMismatch(
            column="amount",
            contract_type="decimal",
            table_type="float",
        )
        assert mismatch.column == "amount"
        assert mismatch.contract_type == "decimal"
        assert mismatch.table_type == "float"

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch_frozen(self) -> None:
        """Test TypeMismatch is immutable."""
        mismatch = TypeMismatch(
            column="id",
            contract_type="string",
            table_type="integer",
        )
        with pytest.raises(ValidationError):
            mismatch.column = "changed"

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch_required_fields(self) -> None:
        """Test TypeMismatch requires all fields."""
        with pytest.raises(ValidationError, match="column"):
            TypeMismatch(  # type: ignore[call-arg]
                contract_type="string",
                table_type="integer",
            )

        with pytest.raises(ValidationError, match="contract_type"):
            TypeMismatch(  # type: ignore[call-arg]
                column="id",
                table_type="integer",
            )


class TestSchemaComparisonResult:
    """Tests for SchemaComparisonResult model (drift detection)."""

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_matches(self) -> None:
        """Test SchemaComparisonResult when schema matches."""
        result = SchemaComparisonResult(
            matches=True,
            type_mismatches=[],
            missing_columns=[],
            extra_columns=[],
        )
        assert result.matches is True
        assert len(result.type_mismatches) == 0
        assert len(result.missing_columns) == 0
        assert len(result.extra_columns) == 0

    @pytest.mark.requirement("3C-FR-022")
    def test_schema_type_mismatch(self) -> None:
        """Test SchemaComparisonResult with type mismatches."""
        result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[
                TypeMismatch(
                    column="price",
                    contract_type="decimal",
                    table_type="double",
                )
            ],
            missing_columns=[],
            extra_columns=[],
        )
        assert result.matches is False
        assert len(result.type_mismatches) == 1

    @pytest.mark.requirement("3C-FR-023")
    def test_schema_missing_columns(self) -> None:
        """Test SchemaComparisonResult with missing columns."""
        result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[],
            missing_columns=["customer_email", "phone_number"],
            extra_columns=[],
        )
        assert result.matches is False
        assert result.missing_columns == ["customer_email", "phone_number"]

    @pytest.mark.requirement("3C-FR-024")
    def test_schema_extra_columns(self) -> None:
        """Test SchemaComparisonResult with extra columns (informational)."""
        result = SchemaComparisonResult(
            matches=True,  # Extra columns are informational, don't affect matches
            type_mismatches=[],
            missing_columns=[],
            extra_columns=["_metadata", "_load_time"],
        )
        assert result.matches is True
        assert result.extra_columns == ["_metadata", "_load_time"]

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_comparison_result_frozen(self) -> None:
        """Test SchemaComparisonResult is immutable."""
        result = SchemaComparisonResult(
            matches=True,
            type_mismatches=[],
            missing_columns=[],
            extra_columns=[],
        )
        with pytest.raises(ValidationError):
            result.matches = False

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_comparison_result_defaults(self) -> None:
        """Test SchemaComparisonResult default values."""
        result = SchemaComparisonResult(matches=True)
        assert result.type_mismatches == []
        assert result.missing_columns == []
        assert result.extra_columns == []


class TestContractViolation:
    """Tests for ContractViolation model (T017)."""

    @pytest.mark.requirement("3C-FR-010")
    def test_contract_violation_minimal(self) -> None:
        """Test creating violation with minimum required fields."""
        violation = ContractViolation(
            error_code="FLOE-E501",
            severity="error",
            message="Element type mismatch",
        )
        assert violation.error_code == "FLOE-E501"
        assert violation.severity == "error"
        assert violation.message == "Element type mismatch"
        assert violation.element_name is None
        assert violation.model_name is None

    @pytest.mark.requirement("3C-FR-010")
    def test_contract_violation_full(self) -> None:
        """Test creating violation with all fields."""
        violation = ContractViolation(
            error_code="FLOE-E502",
            severity="warning",
            message="Missing column in table",
            element_name="customer_email",
            model_name="customers",
            expected="string column",
            actual="column not found",
            suggestion="Add customer_email column to table",
        )
        assert violation.error_code == "FLOE-E502"
        assert violation.severity == "warning"
        assert violation.element_name == "customer_email"
        assert violation.model_name == "customers"
        assert violation.suggestion == "Add customer_email column to table"

    @pytest.mark.requirement("3C-FR-010")
    def test_contract_violation_error_code_pattern(self) -> None:
        """Test that error_code must match FLOE-E5xx pattern."""
        # Valid codes
        ContractViolation(error_code="FLOE-E500", severity="error", message="test")
        ContractViolation(error_code="FLOE-E599", severity="error", message="test")

        # Invalid: wrong prefix
        with pytest.raises(ValidationError, match="String should match pattern"):
            ContractViolation(error_code="FLOE-E400", severity="error", message="test")

        # Invalid: wrong format
        with pytest.raises(ValidationError, match="String should match pattern"):
            ContractViolation(error_code="ERROR-501", severity="error", message="test")

    @pytest.mark.requirement("3C-FR-010")
    def test_contract_violation_severity_literal(self) -> None:
        """Test that severity must be 'error' or 'warning'."""
        # Valid severities
        ContractViolation(error_code="FLOE-E500", severity="error", message="test")
        ContractViolation(error_code="FLOE-E500", severity="warning", message="test")

        # Invalid severity
        with pytest.raises(ValidationError, match="severity"):
            ContractViolation(
                error_code="FLOE-E500",
                severity="info",  # type: ignore[arg-type]
                message="test",
            )

    @pytest.mark.requirement("3C-FR-010")
    def test_contract_violation_frozen(self) -> None:
        """Test that violation is immutable."""
        violation = ContractViolation(
            error_code="FLOE-E500",
            severity="error",
            message="test",
        )
        with pytest.raises(ValidationError):
            violation.message = "changed"


class TestContractValidationResult:
    """Tests for ContractValidationResult model (T017)."""

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_valid(self) -> None:
        """Test creating a valid (passing) validation result."""
        result = ContractValidationResult(
            valid=True,
            violations=[],
            warnings=[],
            schema_hash="sha256:" + "a" * 64,
            validated_at=datetime(2026, 1, 24, 12, 0, 0, tzinfo=timezone.utc),
            contract_name="customers",
            contract_version="1.0.0",
        )
        assert result.valid is True
        assert len(result.violations) == 0
        assert result.error_count == 0
        assert result.warning_count == 0

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_with_violations(self) -> None:
        """Test validation result with errors and warnings."""
        error = ContractViolation(
            error_code="FLOE-E501",
            severity="error",
            message="Type mismatch",
        )
        warning = ContractViolation(
            error_code="FLOE-E510",
            severity="warning",
            message="Extra column in table",
        )
        result = ContractValidationResult(
            valid=False,
            violations=[error],
            warnings=[warning],
            schema_hash="sha256:" + "b" * 64,
            validated_at=datetime(2026, 1, 24, 12, 0, 0, tzinfo=timezone.utc),
            contract_name="orders",
            contract_version="2.0.0",
        )
        assert result.valid is False
        assert len(result.violations) == 1
        assert len(result.warnings) == 1
        assert result.error_count == 1
        assert result.warning_count == 1

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_error_count_property(self) -> None:
        """Test error_count and warning_count properties."""
        errors = [
            ContractViolation(error_code="FLOE-E501", severity="error", message="Error 1"),
            ContractViolation(error_code="FLOE-E502", severity="error", message="Error 2"),
        ]
        warnings_in_violations = [
            ContractViolation(error_code="FLOE-E510", severity="warning", message="Warn 1"),
        ]
        result = ContractValidationResult(
            valid=False,
            violations=errors + warnings_in_violations,
            warnings=[],
            schema_hash="sha256:" + "c" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name="test",
            contract_version="1.0.0",
        )
        assert result.error_count == 2
        assert result.warning_count == 1

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_schema_hash_pattern(self) -> None:
        """Test that schema_hash must match sha256 pattern."""
        # Valid hash
        ContractValidationResult(
            valid=True,
            schema_hash="sha256:" + "0123456789abcdef" * 4,
            validated_at=datetime.now(timezone.utc),
            contract_name="test",
            contract_version="1.0.0",
        )

        # Invalid: wrong prefix
        with pytest.raises(ValidationError, match="String should match pattern"):
            ContractValidationResult(
                valid=True,
                schema_hash="md5:" + "a" * 64,
                validated_at=datetime.now(timezone.utc),
                contract_name="test",
                contract_version="1.0.0",
            )

        # Invalid: wrong length
        with pytest.raises(ValidationError, match="String should match pattern"):
            ContractValidationResult(
                valid=True,
                schema_hash="sha256:abc123",
                validated_at=datetime.now(timezone.utc),
                contract_name="test",
                contract_version="1.0.0",
            )

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_frozen(self) -> None:
        """Test that validation result is immutable."""
        result = ContractValidationResult(
            valid=True,
            schema_hash="sha256:" + "c" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name="test",
            contract_version="1.0.0",
        )
        assert result.valid is True
        with pytest.raises(ValidationError):
            result.valid = False

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_required_fields(self) -> None:
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError, match="valid"):
            ContractValidationResult(  # type: ignore[call-arg]
                schema_hash="sha256:" + "a" * 64,
                validated_at=datetime.now(timezone.utc),
                contract_name="test",
                contract_version="1.0.0",
            )

        with pytest.raises(ValidationError, match="schema_hash"):
            ContractValidationResult(  # type: ignore[call-arg]
                valid=True,
                validated_at=datetime.now(timezone.utc),
                contract_name="test",
                contract_version="1.0.0",
            )

        with pytest.raises(ValidationError, match="contract_name"):
            ContractValidationResult(  # type: ignore[call-arg]
                valid=True,
                schema_hash="sha256:" + "a" * 64,
                validated_at=datetime.now(timezone.utc),
                contract_version="1.0.0",
            )

    @pytest.mark.requirement("3C-FR-010")
    def test_validation_result_default_lists(self) -> None:
        """Test that violations and warnings default to empty lists."""
        result = ContractValidationResult(
            valid=True,
            schema_hash="sha256:" + "d" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name="test",
            contract_version="1.0.0",
        )
        assert result.violations == []
        assert result.warnings == []


__all__ = [
    "TestContractStatus",
    "TestElementType",
    "TestElementFormat",
    "TestClassification",
    "TestTypeMismatch",
    "TestSchemaComparisonResult",
    "TestContractViolation",
    "TestContractValidationResult",
]
