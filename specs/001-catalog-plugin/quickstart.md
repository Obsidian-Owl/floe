# Quickstart: Catalog Plugin

**Feature**: 001-catalog-plugin
**Date**: 2026-01-09
**Status**: Draft

## Overview

This quickstart demonstrates how to use the CatalogPlugin ABC and PolarisCatalogPlugin for Iceberg catalog management in floe.

---

## Prerequisites

1. **Python 3.10+** installed
2. **floe-core** package installed (`pip install floe-core`)
3. **floe-catalog-polaris** plugin installed (`pip install floe-catalog-polaris`)
4. **Polaris server** running (see [Polaris deployment guide](https://polaris.apache.org/))

---

## Quick Example: Connect to Polaris

```python
from floe_core.plugins import get_plugin

# Get the Polaris catalog plugin
catalog = get_plugin("catalog", "polaris")

# Configure connection
config = {
    "uri": "https://polaris.example.com/api/catalog",
    "warehouse": "default_warehouse",
    "oauth2": {
        "client_id": "${POLARIS_CLIENT_ID}",
        "client_secret": "${POLARIS_CLIENT_SECRET}",
        "token_url": "https://polaris.example.com/oauth/token",
    },
}

# Connect to catalog
iceberg_catalog = catalog.connect(config)

# List namespaces
namespaces = catalog.list_namespaces()
print(f"Available namespaces: {namespaces}")
```

---

## Namespace Management

### Create a Namespace

```python
# Create a namespace with properties
catalog.create_namespace(
    namespace="bronze.raw_events",
    properties={
        "location": "s3://data-lake/bronze/raw_events",
        "owner": "data-platform-team",
    },
)
```

### List Namespaces

```python
# List all namespaces
all_namespaces = catalog.list_namespaces()

# List child namespaces under "bronze"
bronze_children = catalog.list_namespaces(parent="bronze")
```

### Delete a Namespace

```python
# Delete an empty namespace
catalog.delete_namespace("bronze.raw_events")
```

---

## Table Operations

### Create a Table

```python
# Define Iceberg schema
schema = {
    "type": "struct",
    "fields": [
        {"id": 1, "name": "event_id", "type": "string", "required": True},
        {"id": 2, "name": "event_time", "type": "timestamp", "required": True},
        {"id": 3, "name": "payload", "type": "string", "required": False},
    ],
}

# Create table in namespace
catalog.create_table(
    identifier="bronze.raw_events",
    schema=schema,
    location="s3://data-lake/bronze/raw_events",
    properties={"format-version": "2"},
)
```

### List Tables

```python
# List tables in a namespace
tables = catalog.list_tables("bronze")
print(f"Tables in bronze: {tables}")
```

### Drop a Table

```python
# Drop table (metadata only)
catalog.drop_table("bronze.raw_events")

# Drop table and purge data files
catalog.drop_table("bronze.raw_events", purge=True)
```

---

## Credential Vending

Get short-lived, scoped credentials for direct table access:

```python
# Vend read credentials
read_creds = catalog.vend_credentials(
    table_path="silver.dim_customers",
    operations=["READ"],
)

print(f"Access key: {read_creds['access_key']}")
print(f"Expires at: {read_creds['expiration']}")

# Vend read/write credentials
write_creds = catalog.vend_credentials(
    table_path="silver.dim_customers",
    operations=["READ", "WRITE"],
)

# Use with PyIceberg or compute engine
# Credentials are scoped to specific table and operations
```

---

## Health Checks

Monitor catalog availability:

```python
from floe_catalog_polaris import PolarisCatalogPlugin

# Check catalog health
status = catalog.health_check(timeout=1.0)

if status.healthy:
    print(f"Catalog OK - response time: {status.response_time_ms}ms")
else:
    print(f"Catalog unhealthy: {status.message}")

# Integrate with monitoring
# status.checked_at provides timestamp for metrics
```

---

## Configuration Reference

### PolarisCatalogConfig

```yaml
# Example floe.yaml configuration
catalog:
  type: polaris
  uri: https://polaris.example.com/api/catalog
  warehouse: default_warehouse
  oauth2:
    client_id: ${POLARIS_CLIENT_ID}
    client_secret: ${POLARIS_CLIENT_SECRET}
    token_url: https://polaris.example.com/oauth/token
    scope: PRINCIPAL_ROLE:ALL  # Optional
    refresh_margin_seconds: 60  # Default: 60
  connect_timeout_seconds: 10  # Default: 10
  read_timeout_seconds: 30  # Default: 30
  max_retries: 5  # Default: 5
  credential_vending_enabled: true  # Default: true
```

### Environment Variables

```bash
# Required for OAuth2 authentication
export POLARIS_CLIENT_ID="your-client-id"
export POLARIS_CLIENT_SECRET="your-client-secret"

# Optional overrides
export POLARIS_URI="https://polaris.example.com/api/catalog"
export POLARIS_WAREHOUSE="default_warehouse"
```

---

## Implementing a Custom Catalog Plugin

To create a custom catalog adapter:

```python
from abc import abstractmethod
from typing import Any

from floe_core.plugins.catalog import CatalogPlugin, Catalog


class MyCatalogPlugin(CatalogPlugin):
    """Custom catalog plugin implementation."""

    name = "my-catalog"
    version = "1.0.0"
    floe_api_version = "2.0.0"

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> Catalog:
        """Connect to your catalog."""
        # Return PyIceberg-compatible Catalog instance
        ...

    @abstractmethod
    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create namespace in your catalog."""
        ...

    @abstractmethod
    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces."""
        ...

    @abstractmethod
    def delete_namespace(self, namespace: str) -> None:
        """Delete empty namespace."""
        ...

    @abstractmethod
    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create Iceberg table."""
        ...

    @abstractmethod
    def list_tables(self, namespace: str) -> list[str]:
        """List tables in namespace."""
        ...

    @abstractmethod
    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop table."""
        ...

    @abstractmethod
    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Vend credentials (raise NotSupportedError if not supported)."""
        ...
```

### Register via Entry Point

```toml
# pyproject.toml
[project.entry-points."floe.catalogs"]
my-catalog = "my_catalog_plugin:MyCatalogPlugin"
```

---

## Error Handling

```python
from floe_core.plugin_errors import (
    CatalogError,
    CatalogUnavailableError,
    AuthenticationError,
    NotSupportedError,
    ConflictError,
    NotFoundError,
)

try:
    catalog.create_namespace("existing_namespace")
except ConflictError:
    print("Namespace already exists")
except AuthenticationError:
    print("Authentication failed - check credentials")
except CatalogUnavailableError:
    print("Catalog service unavailable - will retry")
except NotSupportedError as e:
    print(f"Operation not supported: {e}")
```

---

## OpenTelemetry Integration

All catalog operations emit OpenTelemetry spans automatically:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

# Configure OTel (typically done at application startup)
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

# Catalog operations now emit spans
catalog.create_namespace("bronze")  # Emits: catalog.create_namespace span
catalog.list_tables("bronze")  # Emits: catalog.list_tables span

# Spans include:
# - db.system: "iceberg"
# - floe.catalog.system: "polaris"
# - floe.catalog.warehouse: "default_warehouse"
# - catalog.namespace: "bronze"
# - Operation duration and status
```

---

## Next Steps

1. **Deploy Polaris**: See [Apache Polaris documentation](https://polaris.apache.org/)
2. **Configure OAuth2**: Set up client credentials in your identity provider
3. **Create namespaces**: Organize tables into bronze/silver/gold layers
4. **Register tables**: Use dbt or direct API to register Iceberg tables
5. **Monitor health**: Integrate health checks with your monitoring system

---

## References

- [CatalogPlugin ABC](../../../packages/floe-core/src/floe_core/plugins/catalog.py)
- [PolarisCatalogPlugin](../../../plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
- [Apache Polaris Documentation](https://polaris.apache.org/)
- [Iceberg REST Catalog Spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml)
