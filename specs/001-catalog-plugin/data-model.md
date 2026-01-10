# Data Model: Catalog Plugin

**Feature**: 001-catalog-plugin
**Date**: 2026-01-09
**Status**: Draft

## Overview

This document defines the data model for the CatalogPlugin ABC and PolarisCatalogPlugin implementation. All models use Pydantic v2 with `ConfigDict(frozen=True, extra="forbid")` for immutability and strict validation.

---

## Core Entities

### 1. CatalogPlugin (ABC)

The abstract base class that all catalog implementations must satisfy.

```python
from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from floe_core.plugin_metadata import PluginMetadata


@runtime_checkable
class Catalog(Protocol):
    """Protocol for PyIceberg-compatible catalog interface."""
    def list_namespaces(self) -> list[tuple[str, ...]]: ...
    def list_tables(self, namespace: str) -> list[str]: ...
    def load_table(self, identifier: str) -> Any: ...


class CatalogPlugin(PluginMetadata):
    """Abstract base class for Iceberg catalog plugins."""

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> Catalog:
        """Connect to catalog and return PyIceberg Catalog instance."""
        ...

    @abstractmethod
    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a namespace in the catalog."""
        ...

    @abstractmethod
    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces, optionally under a parent."""
        ...

    @abstractmethod
    def delete_namespace(self, namespace: str) -> None:
        """Delete an empty namespace."""
        ...

    @abstractmethod
    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create an Iceberg table."""
        ...

    @abstractmethod
    def list_tables(self, namespace: str) -> list[str]:
        """List tables in a namespace."""
        ...

    @abstractmethod
    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop a table from the catalog."""
        ...

    @abstractmethod
    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Vend short-lived credentials for table access."""
        ...

    def health_check(self, timeout: float = 1.0) -> "HealthStatus":
        """Check catalog availability (default implementation)."""
        ...
```

**Attributes** (inherited from PluginMetadata):
- `name: str` - Plugin identifier (e.g., "polaris")
- `version: str` - Plugin version (e.g., "1.0.0")
- `floe_api_version: str` - Compatible floe API version (e.g., "2.0.0")

---

### 2. Configuration Models

#### OAuth2Config

```python
from pydantic import BaseModel, ConfigDict, SecretStr, Field

class OAuth2Config(BaseModel):
    """OAuth2 client credentials configuration."""
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
```

#### PolarisCatalogConfig

```python
class PolarisCatalogConfig(BaseModel):
    """Polaris catalog plugin configuration."""
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
```

---

### 3. Namespace

A logical container for tables with hierarchical organization.

```python
class NamespaceProperties(BaseModel):
    """Properties for a catalog namespace."""
    model_config = ConfigDict(frozen=True, extra="allow")  # Allow custom properties

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
    """Catalog namespace representation."""
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
```

**Relationships**:
- Parent/child hierarchy via dot notation
- Contains zero or more tables
- Properties inherited by child namespaces (optional)

---

### 4. TableIdentifier

Uniquely identifies a table within a catalog.

```python
class TableIdentifier(BaseModel):
    """Unique identifier for an Iceberg table."""
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
    def from_string(cls, identifier: str) -> "TableIdentifier":
        """Parse 'namespace.table' string."""
        parts = identifier.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid table identifier: {identifier}")
        return cls(namespace=parts[0], name=parts[1])
```

---

### 5. VendedCredentials

Short-lived credentials returned by `vend_credentials()`.

```python
from datetime import datetime

class VendedCredentials(BaseModel):
    """Temporary credentials for table access."""
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
        """Check if credentials have expired."""
        from datetime import timezone
        return datetime.now(timezone.utc) >= self.expiration

    @property
    def ttl_seconds(self) -> int:
        """Remaining time-to-live in seconds."""
        from datetime import timezone
        delta = self.expiration - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))
```

---

### 6. HealthStatus

Result of catalog health check.

```python
class HealthStatus(BaseModel):
    """Catalog health check result."""
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
```

---

### 7. Error Types

Custom exceptions for catalog operations.

```python
class CatalogError(Exception):
    """Base exception for catalog operations."""
    pass


class CatalogUnavailableError(CatalogError):
    """Catalog service is unreachable."""
    pass


class AuthenticationError(CatalogError):
    """Authentication failed (invalid credentials or token)."""
    pass


class NotSupportedError(CatalogError):
    """Operation not supported by this catalog implementation."""
    pass


class ConflictError(CatalogError):
    """Resource already exists (namespace or table)."""
    pass


class NotFoundError(CatalogError):
    """Resource not found (namespace or table)."""
    pass
```

---

## Entity Relationships

```
┌──────────────────────────────────────────────────────────────────┐
│                        CatalogPlugin (ABC)                       │
│  - name, version, floe_api_version                               │
│  - connect(), create_namespace(), list_namespaces(), ...         │
│  - vend_credentials(), health_check()                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ implements
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    PolarisCatalogPlugin                          │
│  - config: PolarisCatalogConfig                                  │
│  - _catalog: PyIceberg Catalog instance                          │
└──────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌────────────┐    ┌─────────────┐    ┌──────────────────┐
    │ Namespace  │    │ Table       │    │ VendedCredentials│
    │ - name     │◄───│ - namespace │    │ - access_key     │
    │ - props    │    │ - name      │    │ - secret_key     │
    │ - parent   │    │ - schema    │    │ - expiration     │
    └────────────┘    │ - location  │    │ - operations     │
           │          │ - props     │    └──────────────────┘
           │          └─────────────┘
           ▼
    ┌────────────┐
    │ Namespace  │  (child namespace)
    │ - name     │
    │ - parent   │◄─── references parent
    └────────────┘
```

---

## Validation Rules

### Namespace Names
- Start with letter or underscore
- Contain only alphanumeric and underscore
- Dot separates hierarchy levels
- Max 256 characters total
- Case-sensitive

### Table Names
- Start with letter or underscore
- Contain only alphanumeric and underscore
- Max 128 characters
- Case-sensitive

### Credential Vending
- Operations must be non-empty list
- Valid operations: "READ", "WRITE"
- Expiration must be in the future
- TTL max 24 hours (86400 seconds)

### Health Check
- Timeout max 10 seconds
- Response time must be non-negative

---

## State Transitions

### Namespace Lifecycle

```
[Not Exists] ──create_namespace()──► [Exists/Empty]
                                           │
                           create_table()  │
                                           ▼
                                    [Exists/Has Tables]
                                           │
                           drop_table()    │ (all tables)
                                           ▼
                                    [Exists/Empty]
                                           │
                         delete_namespace()│
                                           ▼
                                    [Not Exists]
```

### Credential Lifecycle

```
[No Credentials] ──vend_credentials()──► [Valid]
                                             │
                              time passes    │
                                             ▼
                                        [Expired]
                                             │
                      vend_credentials()     │
                      (new request)          │
                                             ▼
                                        [Valid] (new)
```

---

## JSON Schema Export

All models export JSON Schema for IDE autocomplete:

```python
# Generate JSON Schema
schema = PolarisCatalogConfig.model_json_schema()

# Write to file for IDE support
import json
from pathlib import Path

Path("schemas/polaris-catalog-config.schema.json").write_text(
    json.dumps(schema, indent=2)
)
```

Example schema reference in YAML:
```yaml
# $schema: ./schemas/polaris-catalog-config.schema.json
catalog:
  type: polaris
  uri: https://polaris.example.com/api/catalog
  warehouse: default_warehouse
  # ... IDE provides autocomplete here
```
