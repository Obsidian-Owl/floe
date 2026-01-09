"""Domain models for the Polaris Catalog Plugin.

This module provides Pydantic models for catalog operations including
namespaces, table identifiers, vended credentials, and health status.

Models:
    NamespaceProperties: Metadata properties for namespaces
    Namespace: Catalog namespace representation
    TableIdentifier: Unique identifier for Iceberg tables
    VendedCredentials: Temporary credentials from credential vending
    CatalogHealthStatus: Catalog-specific health check result

Example:
    >>> from floe_catalog_polaris.models import Namespace, TableIdentifier
    >>> ns = Namespace(name="bronze")
    >>> table = TableIdentifier.from_string("bronze.raw_customers")
    >>> table.full_name
    'bronze.raw_customers'
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class NamespaceProperties(BaseModel):
    """Properties for a catalog namespace.

    Supports standard properties (location, owner, comment) and allows
    additional custom properties via extra="allow".

    Attributes:
        location: Storage location for tables in this namespace.
        owner: Owner identifier (user or team).
        comment: Human-readable description.

    Example:
        >>> props = NamespaceProperties(
        ...     location="s3://bucket/bronze",
        ...     owner="data-team",
        ...     comment="Raw ingestion layer"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    location: str | None = Field(
        default=None,
        description="Storage location for tables in this namespace",
        examples=["s3://bucket/bronze", "gs://bucket/silver"],
    )
    owner: str | None = Field(
        default=None,
        description="Owner identifier (user or team)",
    )
    comment: str | None = Field(
        default=None,
        description="Human-readable description",
    )


class Namespace(BaseModel):
    """Catalog namespace representation.

    Namespaces are logical containers for tables with hierarchical
    organization via dot notation (e.g., "silver.customers").

    Attributes:
        name: Full namespace path (dot-separated).
        properties: Namespace metadata properties.
        parent: Parent namespace name (None for root).

    Example:
        >>> ns = Namespace(
        ...     name="silver.customers",
        ...     properties=NamespaceProperties(location="s3://bucket/silver/customers"),
        ...     parent="silver"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description="Full namespace path (dot-separated)",
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$",
        examples=["bronze", "silver.customers", "gold.analytics.reports"],
    )
    properties: NamespaceProperties = Field(
        default_factory=NamespaceProperties,
        description="Namespace metadata properties",
    )
    parent: str | None = Field(
        default=None,
        description="Parent namespace (None for root)",
    )


class TableIdentifier(BaseModel):
    """Unique identifier for an Iceberg table.

    Tables are identified by their namespace and name. The full_name
    property provides the complete path (namespace.table).

    Attributes:
        namespace: Namespace containing the table.
        name: Table name within the namespace.

    Example:
        >>> table = TableIdentifier(namespace="bronze", name="raw_customers")
        >>> table.full_name
        'bronze.raw_customers'

        >>> table = TableIdentifier.from_string("silver.dim_customers")
        >>> table.namespace
        'silver'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(
        ...,
        description="Namespace containing the table",
    )
    name: str = Field(
        ...,
        description="Table name within the namespace",
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )

    @property
    def full_name(self) -> str:
        """Full table identifier (namespace.table)."""
        return f"{self.namespace}.{self.name}"

    @classmethod
    def from_string(cls, identifier: str) -> TableIdentifier:
        """Parse 'namespace.table' string into TableIdentifier.

        Args:
            identifier: Full table identifier string (e.g., "bronze.customers").

        Returns:
            TableIdentifier instance.

        Raises:
            ValueError: If identifier format is invalid.

        Example:
            >>> TableIdentifier.from_string("bronze.customers")
            TableIdentifier(namespace='bronze', name='customers')
        """
        parts = identifier.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid table identifier: {identifier}")
        return cls(namespace=parts[0], name=parts[1])


class VendedCredentials(BaseModel):
    """Temporary credentials for table access.

    Returned by CatalogPlugin.vend_credentials() for secure,
    short-lived access to specific tables and operations.

    Attributes:
        access_key: Temporary access key (e.g., AWS access key ID).
        secret_key: Temporary secret key (stored securely).
        session_token: Session token for AWS STS (if applicable).
        expiration: Credential expiration timestamp (UTC).
        operations: Allowed operations (e.g., ["READ", "WRITE"]).
        table_path: Table path these credentials are scoped to.

    Example:
        >>> from datetime import datetime, timezone, timedelta
        >>> creds = VendedCredentials(
        ...     access_key="ASIA...",
        ...     secret_key="secret",
        ...     session_token="token",
        ...     expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        ...     operations=["READ", "WRITE"],
        ...     table_path="bronze.raw_customers"
        ... )
        >>> creds.is_expired
        False
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    access_key: str = Field(
        ...,
        description="Temporary access key (e.g., AWS access key ID)",
    )
    secret_key: SecretStr = Field(
        ...,
        description="Temporary secret key",
    )
    session_token: SecretStr | None = Field(
        default=None,
        description="Session token (for AWS STS)",
    )
    expiration: datetime = Field(
        ...,
        description="Credential expiration timestamp (UTC)",
    )
    operations: list[str] = Field(
        ...,
        description="Allowed operations (READ, WRITE)",
        min_length=1,
    )
    table_path: str = Field(
        ...,
        description="Table path these credentials are scoped to",
    )

    @property
    def is_expired(self) -> bool:
        """Check if credentials have expired.

        Returns:
            True if current time is at or past expiration.
        """
        return datetime.now(timezone.utc) >= self.expiration

    @property
    def ttl_seconds(self) -> int:
        """Remaining time-to-live in seconds.

        Returns:
            Seconds until expiration (0 if already expired).
        """
        delta = self.expiration - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))


class CatalogHealthStatus(BaseModel):
    """Catalog-specific health check result.

    More detailed than the base HealthStatus in floe-core, this model
    includes response timing and timestamp for monitoring.

    Note: This is separate from floe_core.plugin_metadata.HealthStatus
    which uses HealthState enum. This model is for Polaris-specific
    health check responses.

    Attributes:
        healthy: Whether catalog is responding normally.
        response_time_ms: Health check response time in milliseconds.
        message: Human-readable status message.
        checked_at: Timestamp of health check (UTC).

    Example:
        >>> status = CatalogHealthStatus(
        ...     healthy=True,
        ...     response_time_ms=45.2,
        ...     message="Catalog responding normally"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    healthy: bool = Field(
        ...,
        description="Whether catalog is responding normally",
    )
    response_time_ms: float = Field(
        ...,
        ge=0,
        description="Health check response time in milliseconds",
    )
    message: str = Field(
        ...,
        description="Human-readable status message",
    )
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of health check (UTC)",
    )
