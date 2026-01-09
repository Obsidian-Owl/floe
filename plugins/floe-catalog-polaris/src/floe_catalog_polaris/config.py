"""Configuration models for the Polaris Catalog Plugin.

This module provides Pydantic configuration models for connecting to
Apache Polaris REST catalogs with OAuth2 authentication.

Models:
    OAuth2Config: OAuth2 client credentials configuration
    PolarisCatalogConfig: Complete Polaris catalog connection settings

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
