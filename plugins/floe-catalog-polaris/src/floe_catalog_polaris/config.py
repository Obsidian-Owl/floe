"""Configuration models for the Polaris Catalog Plugin.

This module provides Pydantic configuration models for connecting to
Apache Polaris REST catalogs with OAuth2 authentication.

Models:
    OAuth2Config: OAuth2 client credentials configuration
    PolarisCatalogConfig: Complete Polaris catalog connection settings

Functions:
    export_json_schema: Export JSON Schema for PolarisCatalogConfig

Example:
    >>> from floe_catalog_polaris.config import PolarisCatalogConfig, OAuth2Config
    >>> config = PolarisCatalogConfig(
    ...     uri="https://polaris.example.com/api/catalog",
    ...     warehouse="prod_warehouse",
    ...     oauth2=OAuth2Config(
    ...         client_id="my-client",
    ...         client_secret="secret",
    ...         token_url="https://polaris.example.com/oauth/token"
    ...     )
    ... )

JSON Schema:
    The JSON Schema for PolarisCatalogConfig can be used for IDE autocomplete
    and validation. Add to your YAML file:

    .. code-block:: yaml

        # yaml-language-server: $schema=./schemas/polaris-catalog-config.schema.json
        uri: https://polaris.example.com/api/catalog
        warehouse: prod_warehouse
        ...
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class OAuth2Config(BaseModel):
    """OAuth2 client credentials configuration.

    Configures OAuth2 authentication for Polaris catalog access.
    Uses the client credentials flow (machine-to-machine).

    Attributes:
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret (stored securely).
        token_url: OAuth2 token endpoint URL.
        scope: Optional OAuth2 scope.
        refresh_margin_seconds: Seconds before expiration to refresh token.

    Example:
        >>> oauth = OAuth2Config(
        ...     client_id="polaris-client",
        ...     client_secret="super-secret",
        ...     token_url="https://polaris.example.com/oauth/token",
        ...     scope="PRINCIPAL_ROLE:ALL"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: str = Field(
        ...,
        description="OAuth2 client identifier",
        min_length=1,
    )
    client_secret: SecretStr = Field(
        ...,
        description="OAuth2 client secret (stored securely)",
    )
    token_url: str = Field(
        ...,
        description="OAuth2 token endpoint URL",
        pattern=r"^https?://",
    )
    scope: str | None = Field(
        default=None,
        description="OAuth2 scope (optional)",
    )
    refresh_margin_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Seconds before expiration to refresh token",
    )


class PolarisCatalogConfig(BaseModel):
    """Polaris catalog plugin configuration.

    Complete configuration for connecting to an Apache Polaris REST catalog.
    Includes connection settings, authentication, and operational parameters.

    Attributes:
        uri: Polaris REST API endpoint URL.
        warehouse: Polaris warehouse identifier.
        oauth2: OAuth2 authentication configuration.
        connect_timeout_seconds: Connection timeout in seconds.
        read_timeout_seconds: Read operation timeout in seconds.
        max_retries: Maximum retry attempts for transient failures.
        credential_vending_enabled: Enable X-Iceberg-Access-Delegation header.

    Example:
        >>> config = PolarisCatalogConfig(
        ...     uri="https://polaris.example.com/api/catalog",
        ...     warehouse="default_warehouse",
        ...     oauth2=OAuth2Config(
        ...         client_id="client",
        ...         client_secret="secret",
        ...         token_url="https://polaris.example.com/oauth/token"
        ...     ),
        ...     connect_timeout_seconds=15,
        ...     credential_vending_enabled=True
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str = Field(
        ...,
        description="Polaris REST API endpoint",
        pattern=r"^https?://",
        examples=["https://polaris.example.com/api/catalog"],
    )
    warehouse: str = Field(
        ...,
        description="Polaris warehouse identifier",
        min_length=1,
        examples=["default_warehouse", "prod_iceberg"],
    )
    oauth2: OAuth2Config = Field(
        ...,
        description="OAuth2 authentication configuration",
    )
    connect_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Connection timeout in seconds",
    )
    read_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Read timeout in seconds",
    )
    max_retries: int = Field(
        default=5,
        ge=0,
        le=10,
        description="Maximum retry attempts for transient failures",
    )
    credential_vending_enabled: bool = Field(
        default=True,
        description="Enable X-Iceberg-Access-Delegation header",
    )


def get_json_schema() -> dict[str, object]:
    """Get JSON Schema for PolarisCatalogConfig.

    Returns the JSON Schema representation of the PolarisCatalogConfig model,
    suitable for IDE autocomplete and configuration validation.

    Returns:
        JSON Schema dictionary for PolarisCatalogConfig.

    Example:
        >>> schema = get_json_schema()
        >>> schema["title"]
        'PolarisCatalogConfig'
        >>> "uri" in schema["properties"]
        True
    """
    return PolarisCatalogConfig.model_json_schema()


def export_json_schema(output_path: str | None = None) -> str:
    """Export JSON Schema for PolarisCatalogConfig to file.

    Generates and writes the JSON Schema to the specified path. If no path
    is provided, returns the schema as a JSON string.

    Args:
        output_path: Path to write the schema file. If None, returns JSON string.

    Returns:
        JSON Schema as a string.

    Example:
        >>> # Export to file
        >>> export_json_schema("schemas/polaris-catalog-config.schema.json")
        '{"title": "PolarisCatalogConfig", ...}'

        >>> # Get schema as string
        >>> schema_str = export_json_schema()
        >>> "PolarisCatalogConfig" in schema_str
        True
    """
    import json
    from pathlib import Path

    schema = get_json_schema()
    schema_json = json.dumps(schema, indent=2, sort_keys=False)

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(schema_json + "\n")

    return schema_json
