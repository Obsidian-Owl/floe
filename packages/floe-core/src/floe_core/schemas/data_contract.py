"""Data contract models using Open Data Contract Standard (ODCS).

This module re-exports Pydantic models from the official ODCS package
(open-data-contract-standard) and provides floe-specific validation models.

ODCS v3.1+ is the Linux Foundation standard for data contracts.
See: https://bitol-io.github.io/open-data-contract-standard/

Implements:
    - FR-001: Parse datacontract.yaml files (ODCS v3)
    - FR-002: Validate ODCS v3 schema requirements
    - FR-005: Validate element types match ODCS v3 type system
    - FR-006: Validate model schema completeness
    - FR-007: Validate SLA duration formats (ISO 8601)
    - FR-008: Validate classification values
    - FR-009: Validate format constraints

Tasks: T004, T005, T006, T007, T008, T020
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# Re-export official ODCS models from open-data-contract-standard package
# ==============================================================================

from open_data_contract_standard.model import (  # type: ignore[import-untyped]
    AuthoritativeDefinition,
    CustomProperty,
    DataQuality,
    Description,
    OpenDataContractStandard,
    Pricing,
    Relationship,
    Role,
    SchemaObject,
    SchemaProperty,
    Server,
    ServiceLevelAgreementProperty,
    Support,
    Team,
    TeamMember,
)

# Alias for backwards compatibility and clearer naming
DataContract = OpenDataContractStandard
"""ODCS DataContract model (alias for OpenDataContractStandard).

The official ODCS model provides:
- apiVersion: ODCS version (e.g., "v3.1.0")
- kind: Always "DataContract"
- id: Contract identifier
- version: Contract version (semver)
- status: Lifecycle status (string)
- name: Human-readable name
- domain: Business domain
- description: Description object with purpose, limitations, usage
- schema_: List of SchemaObject (tables/models)
- slaProperties: List of ServiceLevelAgreementProperty
- team: Team or list of TeamMember

Example:
    >>> from floe_core.schemas.data_contract import DataContract
    >>> # Load from YAML using datacontract-cli
    >>> from datacontract.data_contract import DataContract as DC
    >>> dc = DC(data_contract_file="datacontract.yaml")
    >>> contract: DataContract = dc.get_data_contract()
    >>> print(f"Contract: {contract.id} v{contract.version}")
"""

DataContractModel = SchemaObject
"""ODCS SchemaObject (alias for backwards compatibility).

Represents a table/model within a contract with:
- name: Table/model name
- description: Human-readable description
- properties: List of SchemaProperty (columns)
- logicalType: Logical type of the schema object
"""

DataContractElement = SchemaProperty
"""ODCS SchemaProperty (alias for backwards compatibility).

Represents a column/field within a schema with:
- name: Column name
- logicalType: Data type (string, not enum)
- required: Whether non-nullable
- primaryKey: Whether primary key
- unique: Whether unique constraint
- classification: Data classification (string)
"""

# SLA types
FreshnessSLA = ServiceLevelAgreementProperty
"""ODCS ServiceLevelAgreementProperty (alias for SLA).

Used for freshness, availability, quality SLAs with:
- property: SLA property name (e.g., "freshness", "availability")
- value: SLA value (e.g., "PT6H" for 6 hours)
- element: Column to check (for freshness)
"""

QualitySLA = ServiceLevelAgreementProperty
"""ODCS ServiceLevelAgreementProperty (alias for quality SLA)."""

SLAProperties = ServiceLevelAgreementProperty
"""ODCS ServiceLevelAgreementProperty (alias for SLA properties)."""

# Deprecation info is handled via ODCS status field and customProperties
DeprecationInfo = CustomProperty
"""ODCS CustomProperty (used for deprecation metadata)."""

# Contract terms are handled via ODCS Description or customProperties
ContractTerms = CustomProperty
"""ODCS CustomProperty (used for contract terms)."""


# ==============================================================================
# Type constants for ODCS logicalType values
# These are common logical types used in ODCS schema properties
# ==============================================================================

class ElementType:
    """ODCS v3.1 logicalType values.

    These are the only valid logicalType values in ODCS v3.1:
    string, date, timestamp, time, number, integer, object, array, boolean

    Example:
        >>> from floe_core.schemas.data_contract import ElementType
        >>> prop = SchemaProperty(name="id", logicalType=ElementType.STRING)
    """

    # Core ODCS v3.1 logicalTypes
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    TIME = "time"
    ARRAY = "array"
    OBJECT = "object"

    # Aliases for backwards compatibility (mapped to ODCS types)
    INT = "integer"  # Alias for INTEGER
    LONG = "integer"  # Mapped to INTEGER
    FLOAT = "number"  # Mapped to NUMBER
    DOUBLE = "number"  # Mapped to NUMBER
    DECIMAL = "number"  # Mapped to NUMBER


class ElementFormat:
    """Common format constraint values.

    Used with logicalType for additional validation hints.
    """

    EMAIL = "email"
    URI = "uri"
    UUID = "uuid"
    PHONE = "phone"
    DATE = "date"
    DATETIME = "date-time"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class Classification:
    """Common data classification values.

    ODCS uses strings for classification for flexibility.
    These constants provide common values.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"
    PHI = "phi"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class ContractStatus:
    """Common contract status values.

    ODCS uses strings for status for flexibility.
    """

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"
    DRAFT = "draft"


# ==============================================================================
# Floe-specific validation result models (not in ODCS)
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
        >>> from datetime import datetime, timezone
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
    # ODCS models (re-exported from open-data-contract-standard)
    "OpenDataContractStandard",
    "DataContract",  # Alias for OpenDataContractStandard
    "SchemaObject",
    "DataContractModel",  # Alias for SchemaObject
    "SchemaProperty",
    "DataContractElement",  # Alias for SchemaProperty
    "ServiceLevelAgreementProperty",
    "FreshnessSLA",  # Alias
    "QualitySLA",  # Alias
    "SLAProperties",  # Alias
    "Description",
    "Team",
    "TeamMember",
    "Server",
    "Support",
    "Role",
    "Pricing",
    "Relationship",
    "DataQuality",
    "AuthoritativeDefinition",
    "CustomProperty",
    "DeprecationInfo",  # Alias for CustomProperty
    "ContractTerms",  # Alias for CustomProperty
    # Type constants (ODCS uses strings, these provide common values)
    "ElementType",
    "ElementFormat",
    "Classification",
    "ContractStatus",
    # Floe-specific validation models
    "ContractViolation",
    "ContractValidationResult",
    "TypeMismatch",
    "SchemaComparisonResult",
]
