# Data Model: Data Contracts (Epic 3C)

**Date**: 2026-01-24
**Version**: 1.0.0

## Overview

This document defines the Pydantic models for Epic 3C Data Contracts implementation. All models use Pydantic v2 syntax with `frozen=True` and `extra="forbid"` for contract stability.

---

## Core Entities

### DataContract

The main contract model representing an ODCS v3 data contract.

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractStatus(str, Enum):
    """Contract lifecycle status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class DataContract(BaseModel):
    """ODCS v3 data contract representation.

    Represents a formal agreement between data producers and consumers
    defining schema structure, SLAs, and governance requirements.

    Attributes:
        api_version: ODCS schema version (e.g., "v3.0.2")
        kind: Always "DataContract"
        name: Human-readable contract name
        version: Contract version (semver)
        status: Lifecycle status
        owner: Contact email for contract owner
        domain: Business domain
        description: Human-readable description
        models: Schema definitions (tables/objects)
        sla_properties: Service level agreements
        terms: Terms of use
        deprecation: Deprecation info (when status != active)
        tags: Categorization tags
        links: Related URLs
        schema_hash: SHA256 hash of schema (added by floe)
        validated_at: Validation timestamp (added by floe)

    Example:
        >>> contract = DataContract(
        ...     api_version="v3.0.2",
        ...     name="customers",
        ...     version="1.0.0",
        ...     owner="data-team@example.com",
        ...     models=[DataContractModel(name="customers", elements=[...])],
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,  # Allow both camelCase and snake_case
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
```

---

### DataContractModel

Individual model (table/object) within a contract.

```python
class DataContractModel(BaseModel):
    """Individual model (table/object) within a contract.

    Represents a single data structure with its element definitions.

    Attributes:
        name: Model identifier (table name)
        description: Human-readable description
        elements: Column/field definitions

    Example:
        >>> model = DataContractModel(
        ...     name="customers",
        ...     description="Customer master data",
        ...     elements=[
        ...         DataContractElement(name="id", type="string", primary_key=True),
        ...         DataContractElement(name="email", type="string", format="email"),
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
```

---

### DataContractElement

Column/field definition within a model.

```python
class ElementType(str, Enum):
    """ODCS v3 element types."""
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
    """ODCS v3 element formats."""
    EMAIL = "email"
    URI = "uri"
    UUID = "uuid"
    PHONE = "phone"
    DATE = "date"
    DATETIME = "date-time"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class Classification(str, Enum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"
    PHI = "phi"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class DataContractElement(BaseModel):
    """Column/field definition within a model.

    Represents a single column or field with type, constraints,
    and classification information.

    Attributes:
        name: Element identifier (column name)
        type: Data type (string, int, timestamp, etc.)
        required: Whether element is required (non-nullable)
        primary_key: Whether element is primary key
        unique: Whether element values must be unique
        format: Format constraint (email, uri, uuid, etc.)
        classification: Data classification (pii, phi, etc.)
        enum: Allowed values (for string types)
        description: Human-readable description

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
```

---

### SLAProperties

Service level agreement definitions.

```python
class FreshnessSLA(BaseModel):
    """Freshness SLA definition.

    Attributes:
        value: ISO 8601 duration (e.g., "PT6H" for 6 hours)
        element: Column to check for freshness (e.g., "updated_at")
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Annotated[
        str,
        Field(
            pattern=r"^P(?:T?\d+[DHMS])+$",
            description="ISO 8601 duration (e.g., 'PT6H')",
        ),
    ]
    element: str | None = Field(
        default=None,
        description="Column to check for freshness",
    )


class QualitySLA(BaseModel):
    """Quality SLA definition.

    Attributes:
        completeness: Percentage of non-null required fields (e.g., "99%")
        uniqueness: Percentage for primary key columns (e.g., "100%")
        accuracy: Optional accuracy score (e.g., "95%")
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    completeness: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)?%$",
        description="Percentage of non-null required fields",
    )
    uniqueness: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)?%$",
        description="Percentage for primary key columns",
    )
    accuracy: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)?%$",
        description="Optional accuracy score",
    )


class SLAProperties(BaseModel):
    """Service level agreement properties.

    Attributes:
        freshness: Data freshness requirement
        availability: Uptime percentage (e.g., "99.9%")
        quality: Quality thresholds
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    freshness: FreshnessSLA | None = Field(
        default=None,
        description="Data freshness requirement",
    )
    availability: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)?%$",
        description="Uptime percentage (e.g., '99.9%')",
    )
    quality: QualitySLA | None = Field(
        default=None,
        description="Quality thresholds",
    )
```

---

### ContractTerms

Terms and governance information.

```python
class ContractTerms(BaseModel):
    """Contract terms and governance.

    Attributes:
        usage: Intended use cases
        retention: Data retention policy
        pii_handling: PII handling requirements
        limitations: Usage limitations
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
```

---

### DeprecationInfo

Deprecation information for non-active contracts.

```python
class DeprecationInfo(BaseModel):
    """Deprecation information for contracts.

    Attributes:
        announced: Date deprecation was announced
        sunset_date: Date contract will be sunset
        replacement: Replacement contract name
        migration_guide: URL to migration documentation
        reason: Reason for deprecation
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    announced: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date deprecation was announced (ISO 8601)",
    )
    sunset_date: str | None = Field(
        default=None,
        alias="sunsetDate",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date contract will be sunset",
    )
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
```

---

## Validation Result Entities

### ContractValidationResult

Result of contract validation.

```python
class ContractValidationResult(BaseModel):
    """Result of contract validation.

    Attributes:
        valid: Whether contract is valid
        violations: List of validation errors
        warnings: List of validation warnings
        schema_hash: SHA256 hash of contract schema
        validated_at: Timestamp of validation
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool = Field(
        ...,
        description="Whether contract is valid",
    )
    violations: list[Violation] = Field(
        default_factory=list,
        description="Validation errors (FLOE-E5xx)",
    )
    warnings: list[Violation] = Field(
        default_factory=list,
        description="Validation warnings",
    )
    schema_hash: str = Field(
        ...,
        description="SHA256 hash of contract schema",
    )
    validated_at: datetime = Field(
        ...,
        description="Timestamp of validation",
    )
```

---

### SchemaComparisonResult

Result of schema drift detection.

```python
class TypeMismatch(BaseModel):
    """Type mismatch between contract and table.

    Attributes:
        column: Column name
        contract_type: Type in contract
        table_type: Type in table
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    column: str = Field(..., description="Column name")
    contract_type: str = Field(..., description="Type in contract")
    table_type: str = Field(..., description="Type in table")


class SchemaComparisonResult(BaseModel):
    """Result of schema drift detection.

    Attributes:
        matches: Whether schemas match
        type_mismatches: List of type mismatches
        missing_columns: Columns in contract but not in table
        extra_columns: Columns in table but not in contract
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
```

---

## Configuration Entities

### DataContractsConfig

Governance configuration for data contracts.

```python
class DriftDetectionConfig(BaseModel):
    """Schema drift detection configuration.

    Attributes:
        enabled: Whether drift detection is enabled
        enforcement: Enforcement level for drift violations
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Whether drift detection is enabled",
    )
    enforcement: Literal["off", "warn", "strict"] = Field(
        default="warn",
        description="Enforcement level for drift violations",
    )


class DataContractsConfig(BaseModel):
    """Data contracts governance configuration.

    Attributes:
        enforcement: Overall enforcement level
        drift_detection: Schema drift detection settings
        inheritance_mode: How inheritance rules are enforced
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    enforcement: Literal["off", "warn", "strict"] = Field(
        default="warn",
        description="Overall enforcement level",
    )
    drift_detection: DriftDetectionConfig | None = Field(
        default=None,
        alias="driftDetection",
        description="Schema drift detection settings",
    )
    inheritance_mode: Literal["strict", "permissive"] = Field(
        default="strict",
        alias="inheritanceMode",
        description="How inheritance rules are enforced",
    )
```

---

## Entity Relationships

```
DataContract
├── models: list[DataContractModel]
│   └── elements: list[DataContractElement]
├── sla_properties: SLAProperties
│   ├── freshness: FreshnessSLA
│   └── quality: QualitySLA
├── terms: ContractTerms
└── deprecation: DeprecationInfo

DataContractsConfig (in manifest.yaml)
└── drift_detection: DriftDetectionConfig

ContractValidationResult
├── violations: list[Violation]
└── warnings: list[Violation]

SchemaComparisonResult
└── type_mismatches: list[TypeMismatch]
```

---

## Type Mappings

### ODCS Type -> PyIceberg Type

| ODCS Type | PyIceberg Type | Notes |
|-----------|---------------|-------|
| string | STRING | |
| int | INT | 32-bit |
| long | LONG | 64-bit |
| float | FLOAT | 32-bit |
| double | DOUBLE | 64-bit |
| decimal | DECIMAL | Precision/scale from logicalTypeOptions |
| boolean | BOOLEAN | |
| date | DATE | |
| timestamp | TIMESTAMP | With/without timezone |
| time | TIME | |
| bytes | BINARY | |
| array | LIST | Nested element type |
| object | STRUCT | Nested fields |

### ODCS Type -> Python Type (for validation)

| ODCS Type | Python Type |
|-----------|------------|
| string | str |
| int | int |
| long | int |
| float | float |
| double | float |
| decimal | Decimal |
| boolean | bool |
| date | date |
| timestamp | datetime |
| time | time |
| bytes | bytes |
| array | list |
| object | dict |

---

## JSON Schema Export

All models support JSON Schema export via Pydantic:

```python
schema = DataContract.model_json_schema()
```

Schemas will be exported to `specs/3c-data-contracts/contracts/` for IDE autocomplete support.
