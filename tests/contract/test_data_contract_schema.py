"""Contract tests for DataContract schema stability.

Task: T016
Requirements: FR-001, FR-002, FR-005-FR-010

These tests ensure schema stability for DataContract models across versions.
Schema changes that break these tests require a version bump.

Contract tests verify:
1. ODCS re-exports are properly exposed
2. Floe-specific models maintain stable structure
3. Type constants have expected values
4. Serialization works correctly

Note: We use the official ODCS package (open-data-contract-standard) for
DataContract, SchemaObject, SchemaProperty. These tests validate our
integration with that package, not the package itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from floe_core.schemas.data_contract import (
    Classification,
    ContractStatus,
    ContractValidationResult,
    ContractViolation,
    DataContract,
    DataContractElement,
    DataContractModel,
    ElementFormat,
    ElementType,
    SchemaComparisonResult,
    SchemaObject,
    SchemaProperty,
    ServiceLevelAgreementProperty,
    TypeMismatch,
)
from pydantic import ValidationError


class TestODCSReExports:
    """Test that ODCS models are properly re-exported from floe-core."""

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_is_opendata_contract_standard(self) -> None:
        """Test DataContract is the official ODCS model."""
        from open_data_contract_standard.model import OpenDataContractStandard

        assert DataContract is OpenDataContractStandard

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_model_is_schema_object(self) -> None:
        """Test DataContractModel is SchemaObject alias."""
        assert DataContractModel is SchemaObject

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_element_is_schema_property(self) -> None:
        """Test DataContractElement is SchemaProperty alias."""
        assert DataContractElement is SchemaProperty

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_can_be_instantiated(self) -> None:
        """Test that DataContract (OpenDataContractStandard) can be created."""
        # Minimal ODCS v3.1 contract
        contract = DataContract(
            apiVersion="v3.1.0",
            kind="DataContract",
            id="test-contract",
            version="1.0.0",
            status="active",
        )
        assert contract.id == "test-contract"
        assert contract.version == "1.0.0"
        assert contract.apiVersion == "v3.1.0"

    @pytest.mark.requirement("3C-FR-006")
    def test_schema_object_can_be_instantiated(self) -> None:
        """Test that SchemaObject can be created with properties."""
        schema_obj = SchemaObject(
            name="customers",
            description="Customer table",
            properties=[
                SchemaProperty(name="id", logicalType="string"),
                SchemaProperty(name="email", logicalType="string"),
            ],
        )
        assert schema_obj.name == "customers"
        assert len(schema_obj.properties) == 2

    @pytest.mark.requirement("3C-FR-005")
    def test_schema_property_can_be_instantiated(self) -> None:
        """Test that SchemaProperty can be created."""
        prop = SchemaProperty(
            name="email",
            logicalType="string",
            required=True,
            primaryKey=False,
            classification="pii",
        )
        assert prop.name == "email"
        assert prop.logicalType == "string"
        assert prop.classification == "pii"


class TestElementTypeConstants:
    """Test ElementType string constants."""

    @pytest.mark.requirement("3C-FR-005")
    def test_element_type_has_core_odcs_types(self) -> None:
        """Test ElementType has ODCS v3.1 core logicalTypes.

        ODCS v3.1 defines these logicalTypes:
        string, integer, number, boolean, date, timestamp, time, array, object
        """
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
    def test_element_type_has_backward_compat_aliases(self) -> None:
        """Test ElementType provides backward compatibility aliases."""
        # These map to ODCS types
        assert ElementType.INT == "integer"
        assert ElementType.LONG == "integer"
        assert ElementType.FLOAT == "number"
        assert ElementType.DOUBLE == "number"
        assert ElementType.DECIMAL == "number"


class TestElementFormatConstants:
    """Test ElementFormat string constants."""

    @pytest.mark.requirement("3C-FR-009")
    def test_element_format_has_expected_values(self) -> None:
        """Test ElementFormat has common format constraints."""
        assert ElementFormat.EMAIL == "email"
        assert ElementFormat.URI == "uri"
        assert ElementFormat.UUID == "uuid"
        assert ElementFormat.PHONE == "phone"
        assert ElementFormat.DATE == "date"
        assert ElementFormat.DATETIME == "date-time"
        assert ElementFormat.IPV4 == "ipv4"
        assert ElementFormat.IPV6 == "ipv6"


class TestClassificationConstants:
    """Test Classification string constants."""

    @pytest.mark.requirement("3C-FR-008")
    def test_classification_has_expected_values(self) -> None:
        """Test Classification has common data classification values."""
        assert Classification.PUBLIC == "public"
        assert Classification.INTERNAL == "internal"
        assert Classification.CONFIDENTIAL == "confidential"
        assert Classification.PII == "pii"
        assert Classification.PHI == "phi"
        assert Classification.SENSITIVE == "sensitive"
        assert Classification.RESTRICTED == "restricted"


class TestContractStatusConstants:
    """Test ContractStatus string constants."""

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_status_has_lifecycle_states(self) -> None:
        """Test ContractStatus has ODCS lifecycle states."""
        assert ContractStatus.ACTIVE == "active"
        assert ContractStatus.DEPRECATED == "deprecated"
        assert ContractStatus.SUNSET == "sunset"
        assert ContractStatus.RETIRED == "retired"
        assert ContractStatus.DRAFT == "draft"


class TestContractViolationSchemaStability:
    """Contract tests for ContractViolation Pydantic model."""

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_violation_required_fields(self) -> None:
        """Test ContractViolation has expected required fields."""
        schema = ContractViolation.model_json_schema()
        required = set(schema.get("required", []))

        # These fields MUST be required
        expected_required = {"error_code", "severity", "message"}
        assert expected_required == required

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_violation_can_be_instantiated(self) -> None:
        """Test ContractViolation can be created and validated."""
        violation = ContractViolation(
            error_code="FLOE-E501",
            severity="error",
            message="Type mismatch",
            model_name="customers",
            element_name="email",
            expected="string",
            actual="integer",
            suggestion="Update contract schema",
        )
        assert violation.error_code == "FLOE-E501"
        assert violation.severity == "error"

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_violation_error_code_pattern(self) -> None:
        """Test ContractViolation enforces FLOE-E5xx pattern."""
        # Valid pattern
        violation = ContractViolation(
            error_code="FLOE-E500",
            severity="error",
            message="Test",
        )
        assert violation.error_code == "FLOE-E500"

        # Invalid pattern should fail (Pydantic ValidationError)
        with pytest.raises(ValidationError):
            ContractViolation(
                error_code="INVALID",
                severity="error",
                message="Test",
            )

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_violation_serialization_roundtrip(self) -> None:
        """Test ContractViolation serializes and deserializes correctly."""
        original = ContractViolation(
            error_code="FLOE-E502",
            severity="warning",
            message="Missing classification",
            element_name="ssn",
        )

        json_str = original.model_dump_json()
        json_data = json.loads(json_str)
        restored = ContractViolation.model_validate(json_data)

        assert restored.error_code == original.error_code
        assert restored.message == original.message


class TestContractValidationResultSchemaStability:
    """Contract tests for ContractValidationResult Pydantic model."""

    @pytest.mark.requirement("3C-FR-002")
    def test_validation_result_required_fields(self) -> None:
        """Test ContractValidationResult has expected required fields."""
        schema = ContractValidationResult.model_json_schema()
        required = set(schema.get("required", []))

        expected_required = {
            "valid",
            "schema_hash",
            "validated_at",
            "contract_name",
            "contract_version",
        }
        assert expected_required == required

    @pytest.mark.requirement("3C-FR-002")
    def test_validation_result_can_be_instantiated(self) -> None:
        """Test ContractValidationResult can be created."""
        result = ContractValidationResult(
            valid=True,
            violations=[],
            warnings=[],
            schema_hash="sha256:" + "a" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name="test-contract",
            contract_version="1.0.0",
        )
        assert result.valid is True
        assert result.contract_name == "test-contract"

    @pytest.mark.requirement("3C-FR-002")
    def test_validation_result_schema_hash_pattern(self) -> None:
        """Test ContractValidationResult enforces sha256 hash pattern."""
        # Valid pattern
        result = ContractValidationResult(
            valid=True,
            schema_hash="sha256:" + "a" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name="test",
            contract_version="1.0.0",
        )
        assert result.schema_hash.startswith("sha256:")

        # Invalid pattern should fail (Pydantic ValidationError)
        with pytest.raises(ValidationError):
            ContractValidationResult(
                valid=True,
                schema_hash="invalid-hash",
                validated_at=datetime.now(timezone.utc),
                contract_name="test",
                contract_version="1.0.0",
            )

    @pytest.mark.requirement("3C-FR-002")
    def test_validation_result_error_count_property(self) -> None:
        """Test error_count property works correctly."""
        result = ContractValidationResult(
            valid=False,
            violations=[
                ContractViolation(
                    error_code="FLOE-E501",
                    severity="error",
                    message="Error 1",
                ),
                ContractViolation(
                    error_code="FLOE-E502",
                    severity="warning",
                    message="Warning 1",
                ),
                ContractViolation(
                    error_code="FLOE-E503",
                    severity="error",
                    message="Error 2",
                ),
            ],
            schema_hash="sha256:" + "b" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name="test",
            contract_version="1.0.0",
        )
        assert result.error_count == 2
        assert result.warning_count == 1


class TestSchemaComparisonResultStability:
    """Contract tests for drift detection result schemas."""

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_comparison_result_fields(self) -> None:
        """Test SchemaComparisonResult has expected fields."""
        schema = SchemaComparisonResult.model_json_schema()
        properties = schema.get("properties", {})

        expected_fields = {"matches", "type_mismatches", "missing_columns", "extra_columns"}
        actual_fields = set(properties.keys())

        assert expected_fields == actual_fields

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_comparison_result_can_be_instantiated(self) -> None:
        """Test SchemaComparisonResult can be created."""
        result = SchemaComparisonResult(
            matches=False,
            type_mismatches=[
                TypeMismatch(
                    column="email",
                    contract_type="string",
                    table_type="integer",
                )
            ],
            missing_columns=["ssn"],
            extra_columns=["created_at"],
        )
        assert result.matches is False
        assert len(result.type_mismatches) == 1
        assert "ssn" in result.missing_columns

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch_fields(self) -> None:
        """Test TypeMismatch has expected fields."""
        schema = TypeMismatch.model_json_schema()
        properties = schema.get("properties", {})

        expected_fields = {"column", "contract_type", "table_type"}
        actual_fields = set(properties.keys())

        assert expected_fields == actual_fields

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch_is_immutable(self) -> None:
        """Test TypeMismatch is frozen (immutable)."""
        mismatch = TypeMismatch(
            column="id",
            contract_type="string",
            table_type="integer",
        )
        with pytest.raises(ValidationError):
            mismatch.column = "changed"  # type: ignore[misc]


class TestServiceLevelAgreementProperty:
    """Test SLA property re-export from ODCS."""

    @pytest.mark.requirement("3C-FR-007")
    def test_sla_property_can_be_instantiated(self) -> None:
        """Test ServiceLevelAgreementProperty can be created."""
        sla = ServiceLevelAgreementProperty(
            property="freshness",
            value="PT6H",
            element="updated_at",
        )
        assert sla.property == "freshness"
        assert sla.value == "PT6H"


class TestBackwardCompatibility:
    """Tests for backward compatibility guarantees."""

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_with_schema_list(self) -> None:
        """Test that DataContract works with schema list (ODCS v3.1 structure)."""
        # ODCS uses 'schema' as input alias, stored as 'schema_'
        contract = DataContract(
            apiVersion="v3.1.0",
            kind="DataContract",
            id="compat-test",
            version="1.0.0",
            status="active",
            schema=[
                SchemaObject(
                    name="customers",
                    properties=[
                        SchemaProperty(name="id", logicalType="string"),
                    ],
                )
            ],
        )
        # Accessed as schema_ (Python attribute name)
        assert len(contract.schema_) == 1
        assert contract.schema_[0].name == "customers"

    @pytest.mark.requirement("3C-FR-002")
    def test_floe_models_json_schema_export(self) -> None:
        """Test that floe-specific models can export JSON Schema."""
        for model_class in [
            ContractViolation,
            ContractValidationResult,
            TypeMismatch,
            SchemaComparisonResult,
        ]:
            schema = model_class.model_json_schema()
            assert "properties" in schema
            json_str = json.dumps(schema)
            assert len(json_str) > 0


__all__ = [
    "TestODCSReExports",
    "TestElementTypeConstants",
    "TestElementFormatConstants",
    "TestClassificationConstants",
    "TestContractStatusConstants",
    "TestContractViolationSchemaStability",
    "TestContractValidationResultSchemaStability",
    "TestSchemaComparisonResultStability",
    "TestServiceLevelAgreementProperty",
    "TestBackwardCompatibility",
]
