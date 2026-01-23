"""Data contract models for ODCS v3 compliance.

This module provides Pydantic models for data contracts following the
Open Data Contract Standard (ODCS) v3 specification.

Implements:
    - FR-001: Parse datacontract.yaml files (ODCS v3)
    - FR-002: Validate ODCS v3 schema requirements
    - FR-005: Validate element types match ODCS v3 type system
    - FR-006: Validate model schema completeness
    - FR-007: Validate SLA duration formats (ISO 8601)
    - FR-008: Validate classification values
    - FR-009: Validate format constraints

Tasks: T004, T005, T006, T007, T008
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# T008: Enums for ODCS v3 types
# ==============================================================================


class ContractStatus(str, Enum):
    """Contract lifecycle status (ODCS v3).

    Attributes:
        ACTIVE: Contract is active and in use.
        DEPRECATED: Contract is deprecated but still available.
        SUNSET: Contract is being phased out.
        RETIRED: Contract is no longer available.
    """

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class ElementType(str, Enum):
    """ODCS v3 element (column) types.

    Maps to PyIceberg types for schema drift detection.

    Attributes:
        STRING: String/text type.
        INT: 32-bit integer.
        LONG: 64-bit integer.
        FLOAT: 32-bit floating point.
        DOUBLE: 64-bit floating point.
        DECIMAL: Arbitrary precision decimal.
        BOOLEAN: Boolean true/false.
        DATE: Date without time.
        TIMESTAMP: Date with time.
        TIME: Time without date.
        BYTES: Binary data.
        ARRAY: List/array type.
        OBJECT: Nested object/struct.
    """

    STRING = "string"
    INT = "int"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    TIME = "time"
    BYTES = "bytes"
    ARRAY = "array"
    OBJECT = "object"


class ElementFormat(str, Enum):
    """ODCS v3 element format constraints.

    Used for additional validation of string types.

    Attributes:
        EMAIL: Email address format.
        URI: URI/URL format.
        UUID: UUID format.
        PHONE: Phone number format.
        DATE: Date string format.
        DATETIME: ISO 8601 datetime format.
        IPV4: IPv4 address format.
        IPV6: IPv6 address format.
    """

    EMAIL = "email"
    URI = "uri"
    UUID = "uuid"
    PHONE = "phone"
    DATE = "date"
    DATETIME = "date-time"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class Classification(str, Enum):
    """Data classification levels (ODCS v3).

    Used for data governance and access control.

    Attributes:
        PUBLIC: Data is publicly available.
        INTERNAL: Internal use only.
        CONFIDENTIAL: Confidential business data.
        PII: Personally identifiable information.
        PHI: Protected health information.
        SENSITIVE: Sensitive data requiring extra protection.
        RESTRICTED: Highly restricted access.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"
    PHI = "phi"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


# ==============================================================================
# T006: SLA Property Models
# ==============================================================================


class FreshnessSLA(BaseModel):
    """Freshness SLA definition (ODCS v3).

    Defines how fresh data should be, typically measured by a timestamp column.

    Attributes:
        value: ISO 8601 duration (e.g., "PT6H" for 6 hours, "P1D" for 1 day).
        element: Column to check for freshness (e.g., "updated_at").

    Example:
        >>> sla = FreshnessSLA(value="PT6H", element="updated_at")
        >>> sla.value
        'PT6H'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Annotated[
        str,
        Field(
            pattern=r"^P(?:T?\d+[DHMS])+$",
            description="ISO 8601 duration (e.g., 'PT6H' for 6 hours)",
        ),
    ]
    element: str | None = Field(
        default=None,
        description="Column to check for freshness (e.g., 'updated_at')",
    )


class QualitySLA(BaseModel):
    """Quality SLA definition (ODCS v3).

    Defines data quality thresholds for completeness, uniqueness, and accuracy.

    Attributes:
        completeness: Percentage of non-null required fields (e.g., "99%").
        uniqueness: Percentage for primary key uniqueness (e.g., "100%").
        accuracy: Optional accuracy score (e.g., "95%").

    Example:
        >>> sla = QualitySLA(completeness="99%", uniqueness="100%")
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    completeness: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^\d+(\.\d+)?%$",
            description="Percentage of non-null required fields",
        ),
    ]
    uniqueness: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^\d+(\.\d+)?%$",
            description="Percentage for primary key uniqueness",
        ),
    ]
    accuracy: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^\d+(\.\d+)?%$",
            description="Optional accuracy score",
        ),
    ]


class SLAProperties(BaseModel):
    """Service level agreement properties (ODCS v3).

    Combines freshness, availability, and quality SLAs.

    Attributes:
        freshness: Data freshness requirement.
        availability: Uptime percentage (e.g., "99.9%").
        quality: Quality thresholds.

    Example:
        >>> sla = SLAProperties(
        ...     freshness=FreshnessSLA(value="PT6H"),
        ...     availability="99.9%",
        ...     quality=QualitySLA(completeness="99%"),
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    freshness: FreshnessSLA | None = Field(
        default=None,
        description="Data freshness requirement",
    )
    availability: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^\d+(\.\d+)?%$",
            description="Uptime percentage (e.g., '99.9%')",
        ),
    ]
    quality: QualitySLA | None = Field(
        default=None,
        description="Quality thresholds",
    )


# ==============================================================================
# T007: Contract Terms and Deprecation Models
# ==============================================================================


class ContractTerms(BaseModel):
    """Contract terms and governance (ODCS v3).

    Defines usage policies, retention, and handling requirements.

    Attributes:
        usage: Intended use cases.
        retention: Data retention policy.
        pii_handling: PII handling requirements.
        limitations: Usage limitations.

    Example:
        >>> terms = ContractTerms(
        ...     usage="Analytics and reporting",
        ...     retention="7 years",
        ...     pii_handling="Anonymize before export",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    usage: str | None = Field(
        default=None,
        description="Intended use cases",
    )
    retention: str | None = Field(
        default=None,
        description="Data retention policy",
    )
    pii_handling: str | None = Field(
        default=None,
        alias="piiHandling",
        description="PII handling requirements",
    )
    limitations: str | None = Field(
        default=None,
        description="Usage limitations",
    )


class DeprecationInfo(BaseModel):
    """Deprecation information for contracts (ODCS v3).

    Used when contract status is deprecated, sunset, or retired.

    Attributes:
        announced: Date deprecation was announced (ISO 8601).
        sunset_date: Date contract will be sunset.
        replacement: Replacement contract name.
        migration_guide: URL to migration documentation.
        reason: Reason for deprecation.

    Example:
        >>> info = DeprecationInfo(
        ...     announced="2026-01-01",
        ...     sunset_date="2026-06-01",
        ...     replacement="customers-v2",
        ...     reason="Schema redesign for GDPR compliance",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    announced: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="Date deprecation was announced (ISO 8601)",
        ),
    ]
    sunset_date: Annotated[
        str | None,
        Field(
            default=None,
            alias="sunsetDate",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
            description="Date contract will be sunset",
        ),
    ]
    replacement: str | None = Field(
        default=None,
        description="Replacement contract name",
    )
    migration_guide: str | None = Field(
        default=None,
        alias="migrationGuide",
        description="URL to migration documentation",
    )
    reason: str | None = Field(
        default=None,
        description="Reason for deprecation",
    )


# ==============================================================================
# T005: Element and Model Definitions
# ==============================================================================


class DataContractElement(BaseModel):
    """Column/field definition within a model (ODCS v3).

    Represents a single column or field with type, constraints,
    and classification information.

    Attributes:
        name: Element identifier (column name).
        type: Data type (string, int, timestamp, etc.).
        required: Whether element is required (non-nullable).
        primary_key: Whether element is primary key.
        unique: Whether element values must be unique.
        format: Format constraint (email, uri, uuid, etc.).
        classification: Data classification (pii, phi, etc.).
        enum: Allowed values (for string types).
        description: Human-readable description.

    Example:
        >>> element = DataContractElement(
        ...     name="email",
        ...     type=ElementType.STRING,
        ...     required=True,
        ...     format=ElementFormat.EMAIL,
        ...     classification=Classification.PII,
        ...     description="Customer email address",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    name: Annotated[
        str,
        Field(
            min_length=1,
            pattern=r"^[a-z][a-z0-9_]*$",
            description="Element identifier (column name)",
        ),
    ]
    type: ElementType = Field(
        ...,
        description="Data type",
    )
    required: bool = Field(
        default=False,
        description="Whether element is required (non-nullable)",
    )
    primary_key: bool = Field(
        default=False,
        alias="primaryKey",
        description="Whether element is primary key",
    )
    unique: bool = Field(
        default=False,
        description="Whether element values must be unique",
    )
    format: ElementFormat | None = Field(
        default=None,
        description="Format constraint (email, uri, uuid, etc.)",
    )
    classification: Classification | None = Field(
        default=None,
        description="Data classification (pii, phi, etc.)",
    )
    enum: list[str] | None = Field(
        default=None,
        description="Allowed values (for string types)",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )


class DataContractModel(BaseModel):
    """Individual model (table/object) within a contract (ODCS v3).

    Represents a single data structure with its element definitions.

    Attributes:
        name: Model identifier (table name).
        description: Human-readable description.
        elements: Column/field definitions.

    Example:
        >>> model = DataContractModel(
        ...     name="customers",
        ...     description="Customer master data",
        ...     elements=[
        ...         DataContractElement(name="id", type=ElementType.STRING, primary_key=True),
        ...         DataContractElement(name="email", type=ElementType.STRING, format=ElementFormat.EMAIL),
        ...     ],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    name: Annotated[
        str,
        Field(
            min_length=1,
            pattern=r"^[a-z][a-z0-9_]*$",
            description="Model identifier (table name)",
        ),
    ]
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )
    elements: Annotated[
        list[DataContractElement],
        Field(
            min_length=1,
            description="Column/field definitions",
        ),
    ]


# ==============================================================================
# T004: Main DataContract Model
# ==============================================================================


class DataContract(BaseModel):
    """ODCS v3 data contract representation.

    Represents a formal agreement between data producers and consumers
    defining schema structure, SLAs, and governance requirements.

    Attributes:
        api_version: ODCS schema version (e.g., "v3.0.2").
        kind: Always "DataContract".
        name: Human-readable contract name.
        version: Contract version (semver).
        status: Lifecycle status.
        owner: Contact email for contract owner.
        domain: Business domain.
        team: Team name.
        description: Human-readable description.
        models: Schema definitions (tables/objects).
        sla_properties: Service level agreements.
        terms: Terms of use.
        deprecation: Deprecation info (when status != active).
        tags: Categorization tags.
        links: Related URLs.
        schema_hash: SHA256 hash of schema (added by floe).
        validated_at: Validation timestamp (added by floe).

    Example:
        >>> contract = DataContract(
        ...     api_version="v3.0.2",
        ...     name="customers",
        ...     version="1.0.0",
        ...     owner="data-team@example.com",
        ...     models=[DataContractModel(name="customers", elements=[...])],
        ... )

    See Also:
        - ODCS v3 Specification: https://bitol-io.github.io/open-data-contract-standard/
        - FR-001, FR-002: ODCS parsing and validation requirements
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    # Required ODCS fields
    api_version: Annotated[
        str,
        Field(
            alias="apiVersion",
            pattern=r"^v3\.\d+\.\d+$",
            description="ODCS schema version (e.g., 'v3.0.2')",
        ),
    ]
    kind: Literal["DataContract"] = Field(
        default="DataContract",
        description="Resource kind, always 'DataContract'",
    )
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            pattern=r"^[a-z][a-z0-9-]*$",
            description="Contract identifier (DNS-compatible)",
        ),
    ]
    version: Annotated[
        str,
        Field(
            pattern=r"^\d+\.\d+\.\d+$",
            description="Contract version (semver)",
        ),
    ]
    status: ContractStatus = Field(
        default=ContractStatus.ACTIVE,
        description="Lifecycle status",
    )
    owner: Annotated[
        str,
        Field(
            min_length=1,
            description="Contact email for contract owner",
        ),
    ]

    # Optional ODCS fields
    domain: str | None = Field(
        default=None,
        description="Business domain",
    )
    team: str | None = Field(
        default=None,
        description="Team name",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )

    # Schema
    models: Annotated[
        list[DataContractModel],
        Field(
            min_length=1,
            description="Schema definitions (tables/objects)",
        ),
    ]

    # SLA and governance
    sla_properties: SLAProperties | None = Field(
        default=None,
        alias="slaProperties",
        description="Service level agreements",
    )
    terms: ContractTerms | None = Field(
        default=None,
        description="Terms of use",
    )
    deprecation: DeprecationInfo | None = Field(
        default=None,
        description="Deprecation info (when status != active)",
    )

    # Metadata
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags",
    )
    links: dict[str, str] = Field(
        default_factory=dict,
        description="Related URLs (documentation, dashboard, etc.)",
    )

    # Floe-added validation metadata
    schema_hash: str | None = Field(
        default=None,
        description="SHA256 hash of schema (added by floe during validation)",
    )
    validated_at: datetime | None = Field(
        default=None,
        description="Validation timestamp (added by floe)",
    )


# ==============================================================================
# Validation Result Models (T017)
# ==============================================================================


class ContractViolation(BaseModel):
    """A single contract validation violation.

    Self-contained violation model for contract validation results.
    Can be converted to enforcement.Violation for pipeline integration.

    Attributes:
        error_code: FLOE-E5xx format error code.
        severity: "error" or "warning".
        message: Human-readable description.
        element_name: Element (column) name if applicable.
        model_name: Model name where violation occurred.
        expected: What the contract expected.
        actual: What was found.
        suggestion: Remediation advice.

    Example:
        >>> violation = ContractViolation(
        ...     error_code="FLOE-E501",
        ...     severity="error",
        ...     message="Element type mismatch",
        ...     model_name="customers",
        ...     element_name="email",
        ...     expected="string",
        ...     actual="integer",
        ...     suggestion="Update contract or fix table schema",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    error_code: str = Field(
        ...,
        pattern=r"^FLOE-E5\d{2}$",
        description="FLOE-E5xx format error code",
    )
    severity: Literal["error", "warning"] = Field(
        ...,
        description="Severity level",
    )
    message: str = Field(
        ...,
        description="Human-readable description",
    )
    element_name: str | None = Field(
        default=None,
        description="Element (column) name if applicable",
    )
    model_name: str | None = Field(
        default=None,
        description="Model name where violation occurred",
    )
    expected: str | None = Field(
        default=None,
        description="What the contract expected",
    )
    actual: str | None = Field(
        default=None,
        description="What was found",
    )
    suggestion: str | None = Field(
        default=None,
        description="Remediation advice",
    )


class ContractValidationResult(BaseModel):
    """Result of contract validation.

    Contains validation outcome, violations, and metadata for a single
    contract validation run.

    Attributes:
        valid: Whether contract passed validation (no errors).
        violations: List of validation errors (FLOE-E5xx).
        warnings: List of validation warnings.
        schema_hash: SHA256 hash of contract schema for fingerprinting.
        validated_at: Timestamp when validation was performed.
        contract_name: Name of the validated contract.
        contract_version: Version of the validated contract.

    Example:
        >>> result = ContractValidationResult(
        ...     valid=True,
        ...     violations=[],
        ...     warnings=[],
        ...     schema_hash="sha256:abc123...",
        ...     validated_at=datetime.now(timezone.utc),
        ...     contract_name="customers",
        ...     contract_version="1.0.0",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool = Field(
        ...,
        description="Whether contract passed validation (no errors)",
    )
    violations: list[ContractViolation] = Field(
        default_factory=list,
        description="Validation errors (FLOE-E5xx)",
    )
    warnings: list[ContractViolation] = Field(
        default_factory=list,
        description="Validation warnings",
    )
    schema_hash: str = Field(
        ...,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="SHA256 hash of contract schema",
    )
    validated_at: datetime = Field(
        ...,
        description="Timestamp when validation was performed",
    )
    contract_name: str = Field(
        ...,
        description="Name of the validated contract",
    )
    contract_version: str = Field(
        ...,
        description="Version of the validated contract",
    )

    @property
    def error_count(self) -> int:
        """Count of error-severity violations."""
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of warning-severity violations plus warnings list."""
        warn_violations = sum(1 for v in self.violations if v.severity == "warning")
        return warn_violations + len(self.warnings)


class TypeMismatch(BaseModel):
    """Type mismatch between contract and table schema.

    Used in schema drift detection results.

    Attributes:
        column: Column name.
        contract_type: Type defined in contract.
        table_type: Actual type in table.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    column: str = Field(..., description="Column name")
    contract_type: str = Field(..., description="Type defined in contract")
    table_type: str = Field(..., description="Actual type in table")


class SchemaComparisonResult(BaseModel):
    """Result of schema drift detection.

    Attributes:
        matches: Whether schemas match.
        type_mismatches: List of type mismatches.
        missing_columns: Columns in contract but not in table.
        extra_columns: Columns in table but not in contract (info only).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    matches: bool = Field(
        ...,
        description="Whether schemas match",
    )
    type_mismatches: list[TypeMismatch] = Field(
        default_factory=list,
        description="Type mismatches between contract and table",
    )
    missing_columns: list[str] = Field(
        default_factory=list,
        description="Columns in contract but not in table",
    )
    extra_columns: list[str] = Field(
        default_factory=list,
        description="Columns in table but not in contract (info only)",
    )


__all__ = [
    # T008: Enums
    "ContractStatus",
    "ElementType",
    "ElementFormat",
    "Classification",
    # T006: SLA models
    "FreshnessSLA",
    "QualitySLA",
    "SLAProperties",
    # T007: Terms and deprecation
    "ContractTerms",
    "DeprecationInfo",
    # T005: Element and model
    "DataContractElement",
    "DataContractModel",
    # T004: Main contract
    "DataContract",
    # T017: Validation results
    "ContractViolation",
    "ContractValidationResult",
    # Drift detection results
    "TypeMismatch",
    "SchemaComparisonResult",
]
