"""Unit tests for DataContract Pydantic models.

Task: T014
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-005 (Type Validation), FR-006 (Schema Completeness),
              FR-007 (SLA Duration), FR-008 (Classification),
              FR-009 (Format Constraints), FR-010 (Error Codes)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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


class TestContractStatus:
    """Tests for ContractStatus enum."""

    @pytest.mark.requirement("3C-FR-001")
    def test_valid_status_values(self) -> None:
        """Test all valid ContractStatus values."""
        assert ContractStatus.ACTIVE.value == "active"
        assert ContractStatus.DEPRECATED.value == "deprecated"
        assert ContractStatus.SUNSET.value == "sunset"
        assert ContractStatus.RETIRED.value == "retired"

    @pytest.mark.requirement("3C-FR-001")
    def test_status_enum_membership(self) -> None:
        """Test ContractStatus enum membership."""
        statuses = {s.value for s in ContractStatus}
        assert statuses == {"active", "deprecated", "sunset", "retired"}


class TestElementType:
    """Tests for ElementType enum (FR-005)."""

    @pytest.mark.requirement("3C-FR-005")
    def test_odcs_v3_type_system(self) -> None:
        """Test ODCS v3 type system is fully supported."""
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
        assert actual_types == expected_types

    @pytest.mark.requirement("3C-FR-005")
    def test_type_conversion(self) -> None:
        """Test ElementType value conversion."""
        assert ElementType.STRING.value == "string"
        assert ElementType.TIMESTAMP.value == "timestamp"
        assert ElementType.DECIMAL.value == "decimal"


class TestElementFormat:
    """Tests for ElementFormat enum (FR-009)."""

    @pytest.mark.requirement("3C-FR-009")
    def test_format_constraints(self) -> None:
        """Test format constraint values are supported."""
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
        assert actual_formats == expected_formats


class TestClassification:
    """Tests for Classification enum (FR-008)."""

    @pytest.mark.requirement("3C-FR-008")
    def test_classification_values(self) -> None:
        """Test classification values are complete."""
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
        assert actual == expected


class TestDataContractElement:
    """Tests for DataContractElement model."""

    @pytest.mark.requirement("3C-FR-005")
    def test_minimal_element(self) -> None:
        """Test creating element with minimum required fields."""
        element = DataContractElement(
            name="customer_id",
            type=ElementType.STRING,
        )
        assert element.name == "customer_id"
        assert element.type == ElementType.STRING
        assert element.required is False  # default
        assert element.primary_key is False  # default
        assert element.unique is False  # default

    @pytest.mark.requirement("3C-FR-005")
    def test_full_element(self) -> None:
        """Test element with all fields populated."""
        element = DataContractElement(
            name="email",
            type=ElementType.STRING,
            description="Customer email address",
            required=True,
            primary_key=False,
            unique=True,
            format=ElementFormat.EMAIL,
            classification=Classification.PII,
            enum=None,
        )
        assert element.name == "email"
        assert element.format == ElementFormat.EMAIL
        assert element.classification == Classification.PII
        assert element.unique is True

    @pytest.mark.requirement("3C-FR-005")
    def test_element_with_enum_values(self) -> None:
        """Test element with enum constraint."""
        element = DataContractElement(
            name="status",
            type=ElementType.STRING,
            enum=["pending", "active", "completed", "cancelled"],
        )
        assert element.enum == ["pending", "active", "completed", "cancelled"]

    @pytest.mark.requirement("3C-FR-006")
    def test_element_name_required(self) -> None:
        """Test that element name is required."""
        with pytest.raises(ValidationError, match="name"):
            DataContractElement(type=ElementType.STRING)  # type: ignore[call-arg]

    @pytest.mark.requirement("3C-FR-005")
    def test_element_type_required(self) -> None:
        """Test that element type is required."""
        with pytest.raises(ValidationError, match="type"):
            DataContractElement(name="test_field")  # type: ignore[call-arg]

    @pytest.mark.requirement("3C-FR-005")
    def test_element_name_pattern(self) -> None:
        """Test element name must match pattern (lowercase, starts with letter)."""
        # Valid names
        element = DataContractElement(name="customer_id", type=ElementType.STRING)
        assert element.name == "customer_id"

        # Invalid: starts with number
        with pytest.raises(ValidationError, match="String should match pattern"):
            DataContractElement(name="123invalid", type=ElementType.STRING)

        # Invalid: uppercase
        with pytest.raises(ValidationError, match="String should match pattern"):
            DataContractElement(name="InvalidCase", type=ElementType.STRING)


class TestDataContractModel:
    """Tests for DataContractModel."""

    @pytest.mark.requirement("3C-FR-006")
    def test_minimal_model(self) -> None:
        """Test creating model with minimum required fields."""
        model = DataContractModel(
            name="customers",
            elements=[
                DataContractElement(name="id", type=ElementType.STRING),
            ],
        )
        assert model.name == "customers"
        assert len(model.elements) == 1

    @pytest.mark.requirement("3C-FR-006")
    def test_model_with_description(self) -> None:
        """Test model with description."""
        model = DataContractModel(
            name="orders",
            description="Customer orders fact table",
            elements=[
                DataContractElement(name="order_id", type=ElementType.STRING),
                DataContractElement(name="amount", type=ElementType.DECIMAL),
            ],
        )
        assert model.description == "Customer orders fact table"
        assert len(model.elements) == 2

    @pytest.mark.requirement("3C-FR-006")
    def test_model_name_required(self) -> None:
        """Test that model name is required."""
        with pytest.raises(ValidationError, match="name"):
            DataContractModel(  # type: ignore[call-arg]
                elements=[DataContractElement(name="id", type=ElementType.STRING)]
            )

    @pytest.mark.requirement("3C-FR-006")
    def test_model_elements_required(self) -> None:
        """Test that elements list is required."""
        with pytest.raises(ValidationError, match="elements"):
            DataContractModel(name="test")  # type: ignore[call-arg]

    @pytest.mark.requirement("3C-FR-006")
    def test_model_requires_at_least_one_element(self) -> None:
        """Test that model requires at least one element."""
        with pytest.raises(ValidationError, match="at least 1"):
            DataContractModel(name="test", elements=[])


class TestFreshnessSLA:
    """Tests for FreshnessSLA model (FR-007)."""

    @pytest.mark.requirement("3C-FR-007")
    def test_iso8601_duration_valid(self) -> None:
        """Test valid ISO 8601 duration formats."""
        # Hours
        sla = FreshnessSLA(value="PT6H", element="updated_at")
        assert sla.value == "PT6H"

        # Days
        sla = FreshnessSLA(value="P1D", element="loaded_at")
        assert sla.value == "P1D"

        # Minutes
        sla = FreshnessSLA(value="PT30M", element="timestamp")
        assert sla.value == "PT30M"

    @pytest.mark.requirement("3C-FR-007")
    def test_freshness_sla_fields(self) -> None:
        """Test all FreshnessSLA fields."""
        sla = FreshnessSLA(value="PT1H", element="event_time")
        assert sla.value == "PT1H"
        assert sla.element == "event_time"

    @pytest.mark.requirement("3C-FR-007")
    def test_freshness_element_optional(self) -> None:
        """Test that element field is optional."""
        sla = FreshnessSLA(value="PT6H")
        assert sla.value == "PT6H"
        assert sla.element is None


class TestQualitySLA:
    """Tests for QualitySLA model."""

    @pytest.mark.requirement("3C-FR-002")
    def test_quality_sla_defaults(self) -> None:
        """Test QualitySLA default values."""
        sla = QualitySLA()
        assert sla.completeness is None
        assert sla.uniqueness is None
        assert sla.accuracy is None

    @pytest.mark.requirement("3C-FR-002")
    def test_quality_sla_percentages(self) -> None:
        """Test QualitySLA with percentage string values."""
        sla = QualitySLA(completeness="99.5%", uniqueness="100%", accuracy="98%")
        assert sla.completeness == "99.5%"
        assert sla.uniqueness == "100%"
        assert sla.accuracy == "98%"

    @pytest.mark.requirement("3C-FR-002")
    def test_quality_sla_invalid_format(self) -> None:
        """Test QualitySLA rejects invalid percentage format."""
        # Missing % sign
        with pytest.raises(ValidationError, match="String should match pattern"):
            QualitySLA(completeness="99.5")

        # Invalid format
        with pytest.raises(ValidationError, match="String should match pattern"):
            QualitySLA(uniqueness="ninety-nine%")


class TestSLAProperties:
    """Tests for SLAProperties model."""

    @pytest.mark.requirement("3C-FR-007")
    def test_sla_properties_minimal(self) -> None:
        """Test SLAProperties with minimal fields."""
        sla = SLAProperties()
        assert sla.freshness is None
        assert sla.availability is None
        assert sla.quality is None

    @pytest.mark.requirement("3C-FR-007")
    def test_sla_properties_full(self) -> None:
        """Test SLAProperties with all fields."""
        sla = SLAProperties(
            freshness=FreshnessSLA(value="PT6H", element="updated_at"),
            availability="99.9%",
            quality=QualitySLA(completeness="99%", uniqueness="100%"),
        )
        assert sla.freshness is not None
        assert sla.freshness.value == "PT6H"
        assert sla.availability == "99.9%"
        assert sla.quality is not None
        assert sla.quality.completeness == "99%"


class TestContractTerms:
    """Tests for ContractTerms model."""

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_terms_minimal(self) -> None:
        """Test ContractTerms with minimal fields."""
        terms = ContractTerms()
        assert terms.usage is None
        assert terms.limitations is None
        assert terms.retention is None

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_terms_full(self) -> None:
        """Test ContractTerms with all fields."""
        terms = ContractTerms(
            usage="Internal analytics only",
            limitations="Max 1M queries/day",
            retention="7 years",
            pii_handling="Anonymize before export",
        )
        assert terms.usage == "Internal analytics only"
        assert terms.limitations == "Max 1M queries/day"
        assert terms.retention == "7 years"


class TestDeprecationInfo:
    """Tests for DeprecationInfo model."""

    @pytest.mark.requirement("3C-FR-001")
    def test_deprecation_info(self) -> None:
        """Test DeprecationInfo fields."""
        deprecation = DeprecationInfo(
            announced="2026-01-01",
            sunset_date="2026-06-01",
            replacement="new_customers_v2",
            migration_guide="https://docs.example.com/migrate-customers",
            reason="Schema redesign",
        )
        assert deprecation.announced == "2026-01-01"
        assert deprecation.sunset_date == "2026-06-01"
        assert deprecation.replacement == "new_customers_v2"
        assert deprecation.reason == "Schema redesign"

    @pytest.mark.requirement("3C-FR-001")
    def test_deprecation_info_minimal(self) -> None:
        """Test DeprecationInfo with minimal fields."""
        deprecation = DeprecationInfo()
        assert deprecation.announced is None
        assert deprecation.sunset_date is None

    @pytest.mark.requirement("3C-FR-001")
    def test_deprecation_date_format(self) -> None:
        """Test DeprecationInfo date format validation."""
        # Invalid date format
        with pytest.raises(ValidationError, match="String should match pattern"):
            DeprecationInfo(announced="01-01-2026")  # Wrong format

        with pytest.raises(ValidationError, match="String should match pattern"):
            DeprecationInfo(sunset_date="2026/06/01")  # Wrong format


class TestDataContract:
    """Tests for DataContract model (FR-001, FR-002)."""

    @pytest.fixture
    def minimal_contract(self) -> DataContract:
        """Create a minimal valid contract."""
        return DataContract(
            api_version="v3.0.0",
            name="customers",
            version="1.0.0",
            owner="data-team@example.com",
            models=[
                DataContractModel(
                    name="customers",
                    elements=[
                        DataContractElement(name="id", type=ElementType.STRING),
                    ],
                )
            ],
        )

    @pytest.mark.requirement("3C-FR-001")
    def test_minimal_contract(self, minimal_contract: DataContract) -> None:
        """Test creating contract with minimum required fields."""
        assert minimal_contract.name == "customers"
        assert minimal_contract.version == "1.0.0"
        assert minimal_contract.owner == "data-team@example.com"
        assert len(minimal_contract.models) == 1
        assert minimal_contract.api_version == "v3.0.0"
        assert minimal_contract.kind == "DataContract"  # default
        assert minimal_contract.status == ContractStatus.ACTIVE  # default

    @pytest.mark.requirement("3C-FR-002")
    def test_full_contract(self) -> None:
        """Test contract with all ODCS v3 fields populated."""
        contract = DataContract(
            api_version="v3.0.2",
            kind="DataContract",
            version="2.1.0",
            name="orders",
            status=ContractStatus.ACTIVE,
            owner="analytics@example.com",
            domain="sales",
            description="Customer orders data contract",
            models=[
                DataContractModel(
                    name="orders",
                    description="Order fact table",
                    elements=[
                        DataContractElement(
                            name="order_id",
                            type=ElementType.STRING,
                            primary_key=True,
                        ),
                        DataContractElement(
                            name="total_amount",
                            type=ElementType.DECIMAL,
                        ),
                    ],
                )
            ],
            sla_properties=SLAProperties(
                freshness=FreshnessSLA(value="PT6H", element="updated_at"),
                availability="99.9%",
            ),
            terms=ContractTerms(usage="Internal analytics"),
            tags=["production", "gold"],
            links={"documentation": "https://docs.example.com/orders"},
        )
        assert contract.api_version == "v3.0.2"
        assert contract.status == ContractStatus.ACTIVE
        assert contract.domain == "sales"
        assert contract.sla_properties is not None
        assert contract.sla_properties.freshness is not None
        assert contract.tags == ["production", "gold"]

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_api_version_required(self) -> None:
        """Test that contract api_version is required."""
        with pytest.raises(ValidationError, match="apiVersion"):
            DataContract(  # type: ignore[call-arg]
                version="1.0.0",
                name="test",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_version_required(self) -> None:
        """Test that contract version is required."""
        with pytest.raises(ValidationError, match="version"):
            DataContract(  # type: ignore[call-arg]
                api_version="v3.0.0",
                name="test",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_name_required(self) -> None:
        """Test that contract name is required."""
        with pytest.raises(ValidationError, match="name"):
            DataContract(  # type: ignore[call-arg]
                api_version="v3.0.0",
                version="1.0.0",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_owner_required(self) -> None:
        """Test that contract owner is required."""
        with pytest.raises(ValidationError, match="owner"):
            DataContract(  # type: ignore[call-arg]
                api_version="v3.0.0",
                version="1.0.0",
                name="test",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_models_required(self) -> None:
        """Test that at least one model is required."""
        with pytest.raises(ValidationError, match="models"):
            DataContract(  # type: ignore[call-arg]
                api_version="v3.0.0",
                version="1.0.0",
                name="test",
                owner="test@example.com",
            )

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_frozen(self, minimal_contract: DataContract) -> None:
        """Test that contract is immutable (frozen=True)."""
        with pytest.raises(ValidationError):
            minimal_contract.version = "2.0.0"  # type: ignore[misc]

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_extra_forbid(self) -> None:
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError, match="extra"):
            DataContract(
                api_version="v3.0.0",
                version="1.0.0",
                name="test",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
                unexpected_field="should fail",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_deprecation(self) -> None:
        """Test contract with deprecation info."""
        contract = DataContract(
            api_version="v3.0.0",
            version="1.0.0",
            name="customers-v1",
            owner="data-team@example.com",
            status=ContractStatus.DEPRECATED,
            models=[
                DataContractModel(
                    name="customers",
                    elements=[DataContractElement(name="id", type=ElementType.STRING)],
                )
            ],
            deprecation=DeprecationInfo(
                announced="2026-01-01",
                sunset_date="2026-06-01",
                replacement="customers-v2",
            ),
        )
        assert contract.status == ContractStatus.DEPRECATED
        assert contract.deprecation is not None
        assert contract.deprecation.replacement == "customers-v2"

    @pytest.mark.requirement("3C-FR-001")
    def test_contract_validation_metadata(self) -> None:
        """Test contract validation metadata fields."""
        contract = DataContract(
            api_version="v3.0.0",
            version="1.0.0",
            name="test",
            owner="test@example.com",
            models=[
                DataContractModel(
                    name="test",
                    elements=[DataContractElement(name="id", type=ElementType.STRING)],
                )
            ],
            schema_hash="sha256:abc123def456",
            validated_at=datetime(2026, 1, 24, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert contract.schema_hash == "sha256:abc123def456"
        assert contract.validated_at is not None

    @pytest.mark.requirement("3C-FR-002")
    def test_contract_api_version_pattern(self) -> None:
        """Test api_version must match v3.x.x pattern."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            DataContract(
                api_version="v2.0.0",  # Wrong major version
                version="1.0.0",
                name="test",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )


class TestTypeMismatch:
    """Tests for TypeMismatch model (drift detection)."""

    @pytest.mark.requirement("3C-FR-022")
    def test_type_mismatch(self) -> None:
        """Test TypeMismatch for drift detection."""
        mismatch = TypeMismatch(
            column="amount",
            contract_type="decimal",
            table_type="float",
        )
        assert mismatch.column == "amount"
        assert mismatch.contract_type == "decimal"
        assert mismatch.table_type == "float"


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
