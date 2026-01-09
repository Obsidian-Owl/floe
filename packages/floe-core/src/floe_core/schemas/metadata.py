"""Manifest metadata model for manifest schema.

This module provides the ManifestMetadata model for tracking
manifest versions and ownership.

Implements:
    - FR-001: Platform Configuration Definition
    - FR-002: Metadata Validation
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Validation patterns
NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"
"""Pattern for manifest names: lowercase alphanumeric with hyphens, 1-63 chars."""

SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
"""Pattern for semantic version: MAJOR.MINOR.PATCH."""


class ManifestMetadata(BaseModel):
    """Metadata for tracking manifest versions and ownership.

    Provides identification, versioning, and ownership information
    for platform manifests. All manifests require metadata.

    Attributes:
        name: Manifest name (lowercase alphanumeric with hyphens, 1-63 chars)
        version: Semantic version (MAJOR.MINOR.PATCH)
        owner: Owner email address or team name
        description: Optional human-readable description (max 500 chars)

    Example:
        >>> metadata = ManifestMetadata(
        ...     name="acme-platform",
        ...     version="1.0.0",
        ...     owner="platform-team@acme.com",
        ...     description="ACME data platform configuration"
        ... )
        >>> metadata.name
        'acme-platform'

    Validation Rules:
        - V003: name matches pattern ^[a-z0-9][a-z0-9-]*[a-z0-9]$, 1-63 chars
        - V004: version matches semver ^\\d+\\.\\d+\\.\\d+$
        - owner: non-empty string
        - description: max 500 characters

    See Also:
        - data-model.md: ManifestMetadata entity specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "acme-platform",
                    "version": "1.0.0",
                    "owner": "platform-team@acme.com",
                    "description": "ACME data platform configuration",
                }
            ]
        },
    )

    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=63,
            pattern=NAME_PATTERN,
            description="Manifest name (lowercase alphanumeric with hyphens)",
            examples=["acme-platform", "sales-domain"],
        ),
    ]
    version: Annotated[
        str,
        Field(
            pattern=SEMVER_PATTERN,
            description="Semantic version (MAJOR.MINOR.PATCH)",
            examples=["1.0.0", "2.1.3"],
        ),
    ]
    owner: Annotated[
        str,
        Field(
            min_length=1,
            description="Owner email or team name",
            examples=["platform-team@acme.com", "data-engineering"],
        ),
    ]
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Human-readable description",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_reserved(cls, v: str) -> str:
        """Validate that name is not a reserved keyword.

        Args:
            v: The name value to validate

        Returns:
            The validated name

        Raises:
            ValueError: If name is a reserved keyword
        """
        reserved = {"default", "system", "floe", "admin", "root"}
        if v.lower() in reserved:
            msg = f"Name '{v}' is reserved and cannot be used"
            raise ValueError(msg)
        return v


__all__ = [
    "ManifestMetadata",
    "NAME_PATTERN",
    "SEMVER_PATTERN",
]
