"""Configuration model for the Cube semantic layer plugin.

This module defines the CubeSemanticConfig Pydantic model that holds all
configuration for connecting to and configuring a Cube deployment.

Example:
    >>> from floe_semantic_cube.config import CubeSemanticConfig
    >>> config = CubeSemanticConfig(api_secret="my-secret")
    >>> config.server_url
    'http://cube:4000'

Requirements Covered:
    - FR-007: CubeSemanticConfig with server_url, api_secret, database_name
    - FR-045: model_filter_tags for selective schema generation
    - FR-046: model_filter_schemas for schema-based filtering
    - FR-047: health_check_timeout configuration
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class CubeSemanticConfig(BaseModel):
    """Configuration for the Cube semantic layer plugin.

    All fields are validated at construction time. The model is frozen
    (immutable) and rejects unknown fields.

    Args:
        server_url: URL of the Cube API server.
        api_secret: Secret key for Cube API authentication.
        database_name: Logical database name for Cube datasource.
        schema_path: Optional path to Cube schema directory.
        health_check_timeout: Timeout in seconds for health check requests.
        model_filter_tags: dbt model tags to include in schema generation.
        model_filter_schemas: dbt model schemas to include in schema generation.

    Example:
        >>> config = CubeSemanticConfig(
        ...     server_url="http://localhost:4000",
        ...     api_secret="my-secret-key",
        ...     model_filter_tags=["cube", "analytics"],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    server_url: str = Field(
        default="http://cube:4000",
        description="URL of the Cube API server",
    )
    api_secret: SecretStr = Field(
        ...,
        description="Secret key for Cube API authentication",
    )
    database_name: str = Field(
        default="analytics",
        description="Logical database name for Cube datasource",
    )
    schema_path: Path | None = Field(
        default=None,
        description="Optional path to Cube schema directory",
    )
    health_check_timeout: float = Field(
        default=5.0,
        description="Timeout in seconds for health check requests",
    )
    model_filter_tags: list[str] = Field(
        default_factory=list,
        description="dbt model tags to include in schema generation",
    )
    model_filter_schemas: list[str] = Field(
        default_factory=list,
        description="dbt model schemas to include in schema generation",
    )

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, v: str) -> str:
        """Validate that server_url is a valid HTTP(S) URL.

        Args:
            v: The server URL to validate.

        Returns:
            The validated server URL with trailing slash stripped.

        Raises:
            ValueError: If URL doesn't start with http:// or https://.
        """
        v = v.rstrip("/")
        if not v.startswith(("http://", "https://")):
            msg = "server_url must start with http:// or https://"
            raise ValueError(msg)
        return v

    @field_validator("health_check_timeout")
    @classmethod
    def validate_health_check_timeout(cls, v: float) -> float:
        """Validate that health_check_timeout is positive.

        Args:
            v: The timeout value to validate.

        Returns:
            The validated timeout value.

        Raises:
            ValueError: If timeout is not positive.
        """
        if v <= 0:
            msg = "health_check_timeout must be positive"
            raise ValueError(msg)
        return v
