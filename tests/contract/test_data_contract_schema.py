"""Contract tests for DataContract schema stability.

Task: T016
Requirements: FR-001, FR-002, FR-005-FR-010

These tests ensure schema stability for DataContract models across versions.
Schema changes that break these tests require a version bump.

Contract tests verify:
1. Schema structure remains stable (field names, types)
2. JSON Schema can be exported and validated against
3. Serialization/deserialization round-trips correctly
4. Required fields are enforced
5. Optional fields have correct defaults
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from floe_core.schemas.data_contract import (
    Classification,
    ContractStatus,
    ContractTerms,
    DataContract,
    DataContractElement,
    DataContractModel,
    DeprecationInfo,
    ElementFormat,
    ElementType,
    FreshnessSLA,
    QualitySLA,
    SchemaComparisonResult,
    SLAProperties,
    TypeMismatch,
)


class TestDataContractSchemaStability:
    """Contract tests for DataContract schema stability."""

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_required_fields(self) -> None:
        """Test that DataContract has expected required fields.

        Breaking change if any of these fields become optional or removed.
        """
        schema = DataContract.model_json_schema()
        required = set(schema.get("required", []))

        # These fields MUST be required per ODCS v3
        expected_required = {"apiVersion", "name", "version", "owner", "models"}
        assert expected_required.issubset(required), (
            f"Missing required fields: {expected_required - required}"
        )

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_field_types(self) -> None:
        """Test that DataContract field types are stable.

        Breaking change if field types change.
        """
        schema = DataContract.model_json_schema()
        properties = schema.get("properties", {})

        # Verify key field types
        assert properties["apiVersion"]["type"] == "string"
        assert properties["name"]["type"] == "string"
        assert properties["version"]["type"] == "string"
        assert properties["owner"]["type"] == "string"
        assert properties["models"]["type"] == "array"

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_api_version_pattern(self) -> None:
        """Test that apiVersion enforces v3.x.x pattern.

        Breaking change if pattern is relaxed or changed.
        """
        schema = DataContract.model_json_schema()
        api_version_schema = schema["properties"]["apiVersion"]

        assert "pattern" in api_version_schema
        # Pattern must enforce v3.x.x format
        assert "v3" in api_version_schema["pattern"]

    @pytest.mark.requirement("3C-FR-001")
    def test_datacontract_serialization_roundtrip(self) -> None:
        """Test that DataContract serializes and deserializes correctly.

        Ensures no data loss during serialization.
        """
        original = DataContract(
            api_version="v3.0.2",
            name="roundtrip-test",
            version="1.2.3",
            owner="test@example.com",
            domain="analytics",
            description="Test contract for serialization",
            models=[
                DataContractModel(
                    name="test_model",
                    description="Test model",
                    elements=[
                        DataContractElement(
                            name="id",
                            type=ElementType.STRING,
                            required=True,
                            primary_key=True,
                        ),
                        DataContractElement(
                            name="email",
                            type=ElementType.STRING,
                            format=ElementFormat.EMAIL,
                            classification=Classification.PII,
                        ),
                    ],
                )
            ],
            sla_properties=SLAProperties(
                freshness=FreshnessSLA(value="PT6H", element="updated_at"),
                availability="99.9%",
                quality=QualitySLA(completeness="99%", uniqueness="100%"),
            ),
            tags=["test", "contract"],
            links={"docs": "https://example.com"},
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        json_data = json.loads(json_str)

        # Deserialize back
        restored = DataContract.model_validate(json_data)

        # Verify key fields match
        assert restored.api_version == original.api_version
        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.owner == original.owner
        assert restored.domain == original.domain
        assert len(restored.models) == len(original.models)
        assert restored.tags == original.tags

    @pytest.mark.requirement("3C-FR-002")
    def test_datacontract_json_schema_export(self) -> None:
        """Test that JSON Schema can be exported for external validation.

        This schema is used for IDE autocomplete and external tools.
        """
        schema = DataContract.model_json_schema()

        # Must have standard JSON Schema fields
        assert "$defs" in schema or "definitions" in schema or "properties" in schema
        assert "properties" in schema
        assert "required" in schema or len(schema.get("properties", {})) > 0

        # Must be valid JSON (can be serialized)
        json_str = json.dumps(schema)
        assert len(json_str) > 0


class TestDataContractElementSchemaStability:
    """Contract tests for DataContractElement schema stability."""

    @pytest.mark.requirement("3C-FR-005")
    def test_element_required_fields(self) -> None:
        """Test DataContractElement required fields."""
        schema = DataContractElement.model_json_schema()
        required = set(schema.get("required", []))

        # Name and type are always required
        assert "name" in required
        assert "type" in required

    @pytest.mark.requirement("3C-FR-005")
    def test_element_type_enum_values(self) -> None:
        """Test ElementType enum has all ODCS v3 types.

        Breaking change if any type is removed.
        """
        expected_types = {
            "string",
            "int",
            "long",
            "float",
            "double",
            "decimal",
            "boolean",
            "date",
            "timestamp",
            "time",
            "bytes",
            "array",
            "object",
        }
        actual_types = {t.value for t in ElementType}

        assert expected_types == actual_types, (
            f"ElementType mismatch. Missing: {expected_types - actual_types}, "
            f"Extra: {actual_types - expected_types}"
        )

    @pytest.mark.requirement("3C-FR-009")
    def test_element_format_enum_values(self) -> None:
        """Test ElementFormat enum has expected format constraints.

        Breaking change if any format is removed.
        """
        expected_formats = {
            "email",
            "uri",
            "uuid",
            "phone",
            "date",
            "date-time",
            "ipv4",
            "ipv6",
        }
        actual_formats = {f.value for f in ElementFormat}

        assert expected_formats == actual_formats, (
            f"ElementFormat mismatch. Missing: {expected_formats - actual_formats}, "
            f"Extra: {actual_formats - expected_formats}"
        )

    @pytest.mark.requirement("3C-FR-008")
    def test_classification_enum_values(self) -> None:
        """Test Classification enum has expected values.

        Breaking change if any classification is removed.
        """
        expected = {
            "public",
            "internal",
            "confidential",
            "pii",
            "phi",
            "sensitive",
            "restricted",
        }
        actual = {c.value for c in Classification}

        assert expected == actual, (
            f"Classification mismatch. Missing: {expected - actual}, Extra: {actual - expected}"
        )


class TestContractStatusSchemaStability:
    """Contract tests for ContractStatus enum stability."""

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_status_lifecycle(self) -> None:
        """Test ContractStatus has ODCS v3 lifecycle states.

        Breaking change if any status is removed.
        """
        expected_statuses = {"active", "deprecated", "sunset", "retired"}
        actual_statuses = {s.value for s in ContractStatus}

        assert expected_statuses == actual_statuses, (
            f"ContractStatus mismatch. Missing: {expected_statuses - actual_statuses}, "
            f"Extra: {actual_statuses - expected_statuses}"
        )


class TestSLASchemaStability:
    """Contract tests for SLA-related schema stability."""

    @pytest.mark.requirement("3C-FR-007")
    def test_freshness_sla_structure(self) -> None:
        """Test FreshnessSLA schema structure."""
        schema = FreshnessSLA.model_json_schema()
        properties = schema.get("properties", {})

        # Must have value field
        assert "value" in properties
        assert properties["value"]["type"] == "string"

        # Must enforce ISO 8601 duration pattern
        assert "pattern" in properties["value"]

    @pytest.mark.requirement("3C-FR-002")
    def test_quality_sla_fields(self) -> None:
        """Test QualitySLA has expected fields."""
        schema = QualitySLA.model_json_schema()
        properties = schema.get("properties", {})

        # These fields should exist
        expected_fields = {"completeness", "uniqueness", "accuracy"}
        actual_fields = set(properties.keys())

        assert expected_fields.issubset(actual_fields), (
            f"Missing QualitySLA fields: {expected_fields - actual_fields}"
        )

    @pytest.mark.requirement("3C-FR-007")
    def test_sla_properties_structure(self) -> None:
        """Test SLAProperties combines SLA types correctly."""
        schema = SLAProperties.model_json_schema()
        properties = schema.get("properties", {})

        # Must have freshness, availability, and quality
        expected_fields = {"freshness", "availability", "quality"}
        actual_fields = set(properties.keys())

        assert expected_fields.issubset(actual_fields), (
            f"Missing SLAProperties fields: {expected_fields - actual_fields}"
        )


class TestSchemaComparisonResultStability:
    """Contract tests for drift detection result schemas."""

    @pytest.mark.requirement("3C-FR-021")
    def test_schema_comparison_result_fields(self) -> None:
        """Test SchemaComparisonResult has expected fields."""
        schema = SchemaComparisonResult.model_json_schema()
        properties = schema.get("properties", {})

        expected_fields = {"matches", "type_mismatches", "missing_columns", "extra_columns"}
        actual_fields = set(properties.keys())

        assert expected_fields == actual_fields, (
            f"SchemaComparisonResult mismatch. Missing: {expected_fields - actual_fields}, "
            f"Extra: {actual_fields - expected_fields}"
        )

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch_fields(self) -> None:
        """Test TypeMismatch has expected fields."""
        schema = TypeMismatch.model_json_schema()
        properties = schema.get("properties", {})

        expected_fields = {"column", "contract_type", "table_type"}
        actual_fields = set(properties.keys())

        assert expected_fields == actual_fields, (
            f"TypeMismatch mismatch. Missing: {expected_fields - actual_fields}, "
            f"Extra: {actual_fields - expected_fields}"
        )


class TestDeprecationInfoStability:
    """Contract tests for deprecation info schema."""

    @pytest.mark.requirement("3C-FR-001")
    def test_deprecation_info_fields(self) -> None:
        """Test DeprecationInfo has expected fields."""
        schema = DeprecationInfo.model_json_schema()
        properties = schema.get("properties", {})

        # Fields from ODCS v3 deprecation spec
        expected_fields = {"announced", "sunsetDate", "replacement", "migrationGuide", "reason"}
        actual_fields = set(properties.keys())

        assert expected_fields == actual_fields, (
            f"DeprecationInfo mismatch. Missing: {expected_fields - actual_fields}, "
            f"Extra: {actual_fields - expected_fields}"
        )


class TestContractTermsStability:
    """Contract tests for contract terms schema."""

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_terms_fields(self) -> None:
        """Test ContractTerms has expected fields."""
        schema = ContractTerms.model_json_schema()
        properties = schema.get("properties", {})

        # Fields from ODCS v3 terms spec
        expected_fields = {"usage", "retention", "piiHandling", "limitations"}
        actual_fields = set(properties.keys())

        assert expected_fields == actual_fields, (
            f"ContractTerms mismatch. Missing: {expected_fields - actual_fields}, "
            f"Extra: {actual_fields - expected_fields}"
        )


class TestDataContractModelStability:
    """Contract tests for DataContractModel schema."""

    @pytest.mark.requirement("3C-FR-006")
    def test_model_required_fields(self) -> None:
        """Test DataContractModel required fields."""
        schema = DataContractModel.model_json_schema()
        required = set(schema.get("required", []))

        # Name and elements are required
        assert "name" in required
        assert "elements" in required

    @pytest.mark.requirement("3C-FR-006")
    def test_model_elements_min_length(self) -> None:
        """Test DataContractModel requires at least one element."""
        schema = DataContractModel.model_json_schema()
        elements_schema = schema["properties"]["elements"]

        # Must enforce minimum length of 1
        assert elements_schema.get("minItems", 0) >= 1


class TestBackwardCompatibility:
    """Tests for backward compatibility guarantees."""

    @pytest.mark.requirement("3C-FR-001")
    def test_old_format_still_parses(self) -> None:
        """Test that contracts created with earlier schema versions still parse.

        This ensures we don't break existing contracts when evolving the schema.
        """
        # Minimal v3.0.0 format contract
        old_format_data: dict[str, Any] = {
            "apiVersion": "v3.0.0",
            "kind": "DataContract",
            "name": "legacy-contract",
            "version": "1.0.0",
            "owner": "legacy@example.com",
            "models": [
                {
                    "name": "legacy_model",
                    "elements": [
                        {"name": "id", "type": "string"},
                    ],
                }
            ],
        }

        # Should parse without errors
        contract = DataContract.model_validate(old_format_data)
        assert contract.name == "legacy-contract"
        assert contract.api_version == "v3.0.0"

    @pytest.mark.requirement("3C-FR-002")
    def test_optional_fields_have_defaults(self) -> None:
        """Test that all optional fields have sensible defaults.

        Ensures new fields don't break existing contracts.
        """
        # Create contract with only required fields
        contract = DataContract(
            api_version="v3.0.0",
            name="defaults-test",
            version="1.0.0",
            owner="test@example.com",
            models=[
                DataContractModel(
                    name="test",
                    elements=[DataContractElement(name="id", type=ElementType.STRING)],
                )
            ],
        )

        # Verify defaults are set
        assert contract.status == ContractStatus.ACTIVE
        assert contract.kind == "DataContract"
        assert contract.domain is None
        assert contract.team is None
        assert contract.description is None
        assert contract.sla_properties is None
        assert contract.terms is None
        assert contract.deprecation is None
        assert contract.tags == []
        assert contract.links == {}
        assert contract.schema_hash is None
        assert contract.validated_at is None
