"""Configuration models for InfisicalSecretsPlugin.

This module provides Pydantic configuration models for the Infisical Secrets plugin.

Implements:
    - FR-020: InfisicalSecretsPlugin configuration
    - FR-021: Universal Auth authentication
    - CR-003: Configuration schema via Pydantic

Example:
    >>> from pydantic import SecretStr
    >>> from floe_secrets_infisical import InfisicalSecretsConfig
    >>> config = InfisicalSecretsConfig(
    ...     client_id="my-client-id",
    ...     client_secret=SecretStr("my-client-secret"),
    ...     project_id="proj_12345",
    ... )
    >>> config.site_url
    'https://app.infisical.com'
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

# Default Infisical Cloud URL
INFISICAL_CLOUD_URL = "https://app.infisical.com"

# URL pattern for validation (must be HTTPS)
HTTPS_URL_PATTERN = re.compile(r"^https://[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9](?::\d+)?$")


class InfisicalSecretsConfig(BaseModel):
    """Configuration for InfisicalSecretsPlugin.

    This configuration controls how the plugin connects to Infisical
    using Universal Auth credentials.

    Attributes:
        client_id: Universal Auth client ID.
        client_secret: Universal Auth client secret (SecretStr for security).
        site_url: Infisical site URL. Defaults to Infisical Cloud.
        project_id: Infisical project ID. Optional if specified in secrets.
        environment: Environment slug (dev, staging, production, etc.).
        secret_path: Path prefix for secrets. Defaults to root "/".

    Example:
        >>> config = InfisicalSecretsConfig(
        ...     client_id="my-client-id",
        ...     client_secret=SecretStr("my-client-secret"),
        ... )
        >>> config.site_url
        'https://app.infisical.com'

        >>> # Self-hosted Infisical
        >>> config = InfisicalSecretsConfig(
        ...     client_id="my-client-id",
        ...     client_secret=SecretStr("my-client-secret"),
        ...     site_url="https://infisical.company.internal",
        ...     project_id="proj_12345",
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "client_id": "my-client-id",
                    "client_secret": "********",
                    "project_id": "proj_12345",
                },
                {
                    "client_id": "my-client-id",
                    "client_secret": "********",
                    "site_url": "https://infisical.company.internal",
                    "project_id": "proj_12345",
                    "environment": "production",
                    "secret_path": "/floe/databases",
                },
            ]
        },
    )

    client_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Universal Auth client ID",
            examples=["my-client-id", "ua.123456789"],
        ),
    ]

    client_secret: Annotated[
        SecretStr,
        Field(
            min_length=1,
            description="Universal Auth client secret (masked in output)",
            examples=["********"],
        ),
    ]

    site_url: Annotated[
        str,
        Field(
            default=INFISICAL_CLOUD_URL,
            description="Infisical site URL. Defaults to Infisical Cloud.",
            examples=[
                "https://app.infisical.com",
                "https://infisical.company.internal",
            ],
        ),
    ]

    project_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Infisical project ID. Optional if using single-project auth.",
            examples=["proj_12345", "652a1234abcd5678ef901234"],
        ),
    ]

    environment: Annotated[
        str,
        Field(
            default="dev",
            min_length=1,
            description="Environment slug (dev, staging, production, etc.)",
            examples=["dev", "staging", "production", "test"],
        ),
    ]

    secret_path: Annotated[
        str,
        Field(
            default="/",
            description="Path prefix for secrets. Defaults to root.",
            examples=["/", "/floe", "/floe/databases"],
        ),
    ]

    @field_validator("client_secret", mode="before")
    @classmethod
    def convert_to_secret_str(cls, v: str | SecretStr) -> SecretStr:
        """Convert string to SecretStr if needed.

        Args:
            v: The client_secret value.

        Returns:
            SecretStr instance.
        """
        if isinstance(v, SecretStr):
            return v
        return SecretStr(v)

    @field_validator("client_secret")
    @classmethod
    def validate_client_secret_not_empty(cls, v: SecretStr) -> SecretStr:
        """Validate that client_secret is not empty.

        Args:
            v: The client_secret SecretStr.

        Returns:
            Validated SecretStr.

        Raises:
            ValueError: If client_secret is empty.
        """
        if not v.get_secret_value():
            msg = "client_secret cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("site_url")
    @classmethod
    def validate_site_url(cls, v: str) -> str:
        """Validate and normalize site URL.

        Ensures URL uses HTTPS and strips trailing slashes.

        Args:
            v: The site URL value.

        Returns:
            Normalized URL string.

        Raises:
            ValueError: If URL is invalid or not HTTPS.
        """
        # Strip trailing slashes
        v = v.rstrip("/")

        # Must be HTTPS for security
        if not v.startswith("https://"):
            msg = "site_url must use HTTPS for security"
            raise ValueError(msg)

        # Basic URL validation
        if not HTTPS_URL_PATTERN.match(v):
            msg = f"Invalid site URL format: {v}"
            raise ValueError(msg)

        return v

    @field_validator("secret_path")
    @classmethod
    def normalize_secret_path(cls, v: str) -> str:
        """Normalize secret path to have leading slash.

        Args:
            v: The secret path value.

        Returns:
            Normalized path with leading slash.
        """
        if not v.startswith("/"):
            v = f"/{v}"
        return v


__all__ = ["InfisicalSecretsConfig", "INFISICAL_CLOUD_URL"]
