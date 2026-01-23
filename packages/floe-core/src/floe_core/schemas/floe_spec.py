"""FloeSpec schema models for data product configuration.

This module provides Pydantic models for validating and working with
FloeSpec (floe.yaml) - the data engineer's configuration file.

FloeSpec defines a single data product with:
- Metadata (name, version, owner)
- Platform reference (manifest location)
- Transform specifications (dbt models)
- Optional scheduling configuration

Implements:
    - FR-003: FloeSpec Parsing
    - FR-014: Environment-agnostic configuration

Example:
    >>> from floe_core.schemas import FloeSpec
    >>> import yaml
    >>> with open("floe.yaml") as f:
    ...     data = yaml.safe_load(f)
    >>> spec = FloeSpec.model_validate(data)
    >>> print(f"Product: {spec.metadata.name}")

See Also:
    - specs/2b-compilation-pipeline/spec.md: Feature specification
    - specs/2b-compilation-pipeline/data-model.md: Data model documentation
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Validation patterns
FLOE_NAME_PATTERN = r"^[a-z][a-z0-9-]*$"
"""Pattern for FloeSpec names: DNS-compatible, starts with letter (C001)."""

SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
"""Pattern for semantic version: MAJOR.MINOR.PATCH (C002)."""

DBT_MODEL_NAME_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
"""Pattern for dbt model names: alphanumeric with underscores (C005)."""

# Forbidden fields that indicate environment-specific configuration (FR-014)
FORBIDDEN_ENVIRONMENT_FIELDS = frozenset(
    {
        "database",
        "schema",
        "host",
        "port",
        "username",
        "password",
        "credentials",
        "connection_string",
        "endpoint",
        "access_key",
        "secret_key",
        "token",
        "api_key",
    }
)
"""Fields that must not appear in FloeSpec (environment-agnostic, C004)."""


class FloeMetadata(BaseModel):
    """Metadata for a FloeSpec data product.

    Provides identification and ownership information for data products.
    Names must be DNS-compatible and versions must follow semver.

    Attributes:
        name: Product name (DNS-compatible: lowercase, starts with letter)
        version: Product version (semver: MAJOR.MINOR.PATCH)
        description: Optional human-readable description
        owner: Optional owner email or team name
        labels: Optional key-value labels for categorization

    Example:
        >>> metadata = FloeMetadata(
        ...     name="customer-analytics",
        ...     version="1.0.0",
        ...     owner="analytics-team@acme.com",
        ...     description="Customer behavior analytics pipeline"
        ... )
        >>> metadata.name
        'customer-analytics'

    Validation Rules:
        - C001: name matches ^[a-z][a-z0-9-]*$ (DNS-compatible)
        - C002: version matches semver ^\\d+\\.\\d+\\.\\d+$

    See Also:
        - data-model.md: FloeMetadata entity specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "customer-analytics",
                    "version": "1.0.0",
                    "owner": "analytics-team@acme.com",
                    "description": "Customer behavior analytics pipeline",
                    "labels": {"domain": "analytics", "tier": "gold"},
                }
            ]
        },
    )

    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=63,
            pattern=FLOE_NAME_PATTERN,
            description="Product name (DNS-compatible: lowercase, starts with letter)",
            examples=["customer-analytics", "sales-pipeline"],
        ),
    ]
    version: Annotated[
        str,
        Field(
            pattern=SEMVER_PATTERN,
            description="Product version (semver: MAJOR.MINOR.PATCH)",
            examples=["1.0.0", "2.1.3"],
        ),
    ]
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Human-readable description",
    )
    owner: str | None = Field(
        default=None,
        min_length=1,
        description="Owner email or team name",
        examples=["analytics-team@acme.com", "data-engineering"],
    )
    labels: dict[str, str] | None = Field(
        default=None,
        description="Key-value labels for categorization",
        examples=[{"domain": "analytics", "tier": "gold"}],
    )


class TransformSpec(BaseModel):
    """Configuration for a single dbt model/transform.

    Defines a transform within a data product, specifying the model name,
    optional compute target override, tags, and dependencies.

    Attributes:
        name: Model name (must exist in dbt project, matches dbt naming)
        compute: Optional compute target override (None = platform default)
        tags: Optional list of dbt tags for selection
        depends_on: Optional list of explicit dependencies (model names)

    Example:
        >>> transform = TransformSpec(
        ...     name="stg_customers",
        ...     compute="duckdb",
        ...     tags=["staging", "customers"],
        ...     depends_on=["raw_customers"]
        ... )
        >>> transform.name
        'stg_customers'

    Validation Rules:
        - C005: name matches ^[a-zA-Z_][a-zA-Z0-9_]*$ (dbt model naming)
        - C006: compute must be in platform's approved_plugins (validated at compilation)

    See Also:
        - data-model.md: TransformSpec entity specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "stg_customers",
                    "compute": "duckdb",
                    "tags": ["staging", "customers"],
                    "depends_on": ["raw_customers"],
                }
            ]
        },
    )

    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            pattern=DBT_MODEL_NAME_PATTERN,
            description="Model name (dbt naming convention)",
            examples=["stg_customers", "fct_orders"],
        ),
    ]
    compute: str | None = Field(
        default=None,
        description="Compute target override (None = platform default)",
        examples=["duckdb", "snowflake"],
    )
    tags: list[str] | None = Field(
        default=None,
        description="dbt tags for selection",
        examples=[["staging", "customers"]],
    )
    depends_on: Annotated[
        list[str] | None,
        Field(
            default=None,
            alias="dependsOn",
            description="Explicit dependencies (model names)",
            examples=[["raw_customers", "raw_orders"]],
        ),
    ]


class ScheduleSpec(BaseModel):
    """Scheduling configuration for the data product.

    Defines when and how the data product pipeline should run.
    Supports cron expressions and timezone configuration.

    Attributes:
        cron: Cron expression for scheduling (e.g., "0 6 * * *")
        timezone: IANA timezone (default: UTC)
        enabled: Whether schedule is active (default: true)

    Example:
        >>> schedule = ScheduleSpec(
        ...     cron="0 6 * * *",
        ...     timezone="America/New_York",
        ...     enabled=True
        ... )
        >>> schedule.cron
        '0 6 * * *'

    See Also:
        - data-model.md: ScheduleSpec entity specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "cron": "0 6 * * *",
                    "timezone": "America/New_York",
                    "enabled": True,
                }
            ]
        },
    )

    cron: str | None = Field(
        default=None,
        description="Cron expression for scheduling",
        examples=["0 6 * * *", "0 */4 * * *"],
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone",
        examples=["UTC", "America/New_York", "Europe/London"],
    )
    enabled: bool = Field(
        default=True,
        description="Whether schedule is active",
    )


class PlatformRef(BaseModel):
    """Reference to a platform manifest.

    Points to the platform configuration that governs this data product.
    Can be an OCI URI or local file path.

    Attributes:
        manifest: OCI URI or local path to manifest.yaml

    Example:
        >>> ref = PlatformRef(manifest="oci://registry.acme.com/manifests/platform:1.0")
        >>> ref.manifest
        'oci://registry.acme.com/manifests/platform:1.0'

    See Also:
        - data-model.md: PlatformRef entity specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"manifest": "oci://registry.acme.com/manifests/platform:1.0"},
                {"manifest": "./manifest.yaml"},
            ]
        },
    )

    manifest: Annotated[
        str,
        Field(
            min_length=1,
            description="OCI URI or local path to manifest",
            examples=["oci://registry.acme.com/manifests/platform:1.0", "./manifest.yaml"],
        ),
    ]


class FloeSpec(BaseModel):
    """Data product configuration from floe.yaml.

    The main schema for data engineer's product definition. Contains
    metadata, platform reference, transforms, and optional scheduling.

    Attributes:
        api_version: API version for schema compatibility ("floe.dev/v1")
        kind: Resource kind discriminator ("FloeSpec")
        metadata: Product metadata (name, version, owner)
        platform: Optional reference to platform manifest
        transforms: List of dbt models/transforms (at least one required)
        schedule: Optional scheduling configuration

    Example:
        >>> spec = FloeSpec(
        ...     apiVersion="floe.dev/v1",
        ...     kind="FloeSpec",
        ...     metadata=FloeMetadata(name="analytics", version="1.0.0"),
        ...     transforms=[TransformSpec(name="stg_customers")]
        ... )
        >>> spec.metadata.name
        'analytics'

    Validation Rules:
        - C001: metadata.name must be DNS-compatible
        - C002: metadata.version must be valid semver
        - C003: transforms must have at least one entry
        - C004: No environment-specific fields allowed (FR-014)

    See Also:
        - data-model.md: FloeSpec entity specification
        - specs/2b-compilation-pipeline/spec.md: Feature specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "apiVersion": "floe.dev/v1",
                    "kind": "FloeSpec",
                    "metadata": {
                        "name": "customer-analytics",
                        "version": "1.0.0",
                        "owner": "analytics-team@acme.com",
                    },
                    "platform": {"manifest": "./manifest.yaml"},
                    "transforms": [
                        {"name": "stg_customers"},
                        {"name": "fct_orders", "dependsOn": ["stg_customers"]},
                    ],
                }
            ]
        },
    )

    api_version: Annotated[
        Literal["floe.dev/v1"],
        Field(
            alias="apiVersion",
            description="API version for schema compatibility",
        ),
    ]
    kind: Literal["FloeSpec"] = Field(
        description="Resource kind discriminator",
    )
    metadata: FloeMetadata = Field(
        description="Product metadata (name, version, owner)",
    )
    platform: PlatformRef | None = Field(
        default=None,
        description="Reference to platform manifest (OCI URI or local path)",
    )
    transforms: Annotated[
        list[TransformSpec],
        Field(
            min_length=1,
            description="List of dbt models/transforms (at least one required)",
        ),
    ]
    schedule: ScheduleSpec | None = Field(
        default=None,
        description="Optional scheduling configuration",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_no_environment_fields(cls, data: Any) -> Any:
        """Validate that no environment-specific fields are present (C004, FR-014).

        Args:
            data: Raw input data (may be dict or other type from Pydantic)

        Returns:
            Validated data

        Raises:
            ValueError: If forbidden environment fields are found
        """
        if not isinstance(data, dict):
            return data

        # At this point we know data is a dict
        data_dict: dict[str, Any] = data
        forbidden_found = _find_forbidden_fields(data_dict)
        if forbidden_found:
            fields_str = ", ".join(sorted(forbidden_found))
            msg = (
                f"Environment-specific fields are not allowed in FloeSpec: {fields_str}. "
                "Use platform manifest for environment configuration (FR-014)."
            )
            raise ValueError(msg)
        return data

    @field_validator("transforms")
    @classmethod
    def validate_unique_transform_names(cls, v: list[TransformSpec]) -> list[TransformSpec]:
        """Validate that transform names are unique.

        Args:
            v: List of TransformSpec objects

        Returns:
            Validated list of TransformSpec objects

        Raises:
            ValueError: If duplicate transform names are found
        """
        names = [t.name for t in v]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            msg = f"Duplicate transform names are not allowed: {', '.join(sorted(duplicates))}"
            raise ValueError(msg)
        return v


def _find_forbidden_in_list(items: list[Any], base_path: str) -> set[str]:
    """Find forbidden fields in list items recursively.

    Args:
        items: List to search through.
        base_path: Path prefix for error reporting.

    Returns:
        Set of forbidden field paths found in list items.
    """
    forbidden_found: set[str] = set()
    for i, list_item in enumerate(items):
        if isinstance(list_item, dict):
            forbidden_found.update(_find_forbidden_fields(dict(list_item), f"{base_path}[{i}]"))
    return forbidden_found


def _find_forbidden_fields(
    data: dict[str, Any],
    path: str = "",
) -> set[str]:
    """Recursively find forbidden environment-specific fields.

    Args:
        data: Dictionary to search
        path: Current path for error reporting

    Returns:
        Set of forbidden field paths found
    """
    forbidden_found: set[str] = set()

    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if key.lower() in FORBIDDEN_ENVIRONMENT_FIELDS:
            forbidden_found.add(current_path)

        if isinstance(value, dict):
            forbidden_found.update(_find_forbidden_fields(dict(value), current_path))
        elif isinstance(value, list):
            forbidden_found.update(_find_forbidden_in_list(value, current_path))

    return forbidden_found


__all__ = [
    "FloeMetadata",
    "TransformSpec",
    "ScheduleSpec",
    "PlatformRef",
    "FloeSpec",
    "FLOE_NAME_PATTERN",
    "SEMVER_PATTERN",
    "DBT_MODEL_NAME_PATTERN",
    "FORBIDDEN_ENVIRONMENT_FIELDS",
]
