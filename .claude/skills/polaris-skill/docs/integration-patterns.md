# Apache Polaris Integration Patterns (floe-runtime)

This document provides detailed integration patterns for Apache Polaris within the floe-runtime architecture.

## Table of Contents

1. [Platform Configuration](#platform-configuration)
2. [Pipeline Configuration](#pipeline-configuration)
3. [floe-polaris Client Usage](#floe-polaris-client-usage)
4. [dbt-duckdb Plugin Integration](#dbt-duckdb-plugin-integration)
5. [Helm Chart Initialization](#helm-chart-initialization)
6. [Multi-Engine Access Patterns](#multi-engine-access-patterns)

---

## Platform Configuration

### Location
`platform/<env>/platform.yaml`

### Full Example (Local Environment)

```yaml
# platform/local/platform.yaml
version: "1.1.0"

catalogs:
  default:
    type: polaris
    uri: "http://floe-infra-polaris:8181/api/catalog"
    warehouse: demo_catalog
    namespace: default
    credentials:
      mode: oauth2
      client_id:
        secret_ref: polaris-client-id    # Resolved from POLARIS_CLIENT_ID env var
      client_secret:
        secret_ref: polaris-client-secret # Resolved from POLARIS_CLIENT_SECRET env var
      scope: "PRINCIPAL_ROLE:service_admin"
    access_delegation: none               # Disable vended credentials for LocalStack
    token_refresh_enabled: true
```

### Credential Resolution Order

1. **Environment variable**: `POLARIS_CLIENT_SECRET`
2. **K8s secret mount**: `/var/run/secrets/polaris-client-secret`

### Access Delegation Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `none` | Disable vended credentials | LocalStack/MinIO (static S3 credentials) |
| `vended-credentials` | AWS STS AssumeRole | Production AWS with IAM roles |
| `""` (empty string) | Auto-detect | Disables when `s3_endpoint` is set |

### Multi-Environment Example

```yaml
# platform/dev/platform.yaml
catalogs:
  default:
    type: polaris
    uri: "https://polaris-dev.example.com/api/catalog"
    warehouse: dev_catalog
    credentials:
      mode: oauth2
      scope: "PRINCIPAL_ROLE:data_engineer"
    access_delegation: vended-credentials  # Use AWS STS in cloud

# platform/prod/platform.yaml
catalogs:
  default:
    type: polaris
    uri: "https://polaris-prod.example.com/api/catalog"
    warehouse: prod_catalog
    credentials:
      mode: oauth2
      scope: "PRINCIPAL_ROLE:data_analyst"  # Read-only in production
    access_delegation: vended-credentials
```

---

## Pipeline Configuration

### Location
`floe.yaml` (pipeline root)

### Data Engineer Experience

```yaml
# floe.yaml (Data Engineer - NO credentials)
name: customer-analytics
version: "1.0.0"

# Logical references - resolved at compile time from platform.yaml
storage: default      # References platform.yaml storage.default
catalog: default      # References platform.yaml catalogs.default
compute: default      # References platform.yaml compute.default

transforms:
  - type: dbt
    path: "."
    target: prod
```

### What Data Engineers NEVER Configure

- ❌ Polaris endpoints (URIs)
- ❌ OAuth2 credentials (client_id, client_secret)
- ❌ Storage endpoints (S3, LocalStack)
- ❌ S3 access keys
- ❌ Access delegation modes

**The same `floe.yaml` works across all environments** (local, dev, staging, prod).

---

## floe-polaris Client Usage

### Package
`packages/floe-polaris`

### Option 1: From PolarisCatalogConfig (Native)

```python
from floe_polaris import create_catalog, PolarisCatalogConfig
from pydantic import SecretStr

config = PolarisCatalogConfig(
    uri="http://polaris:8181/api/catalog",
    warehouse="demo_catalog",
    client_id="demo_client",
    client_secret=SecretStr("demo_secret"),
    scope="PRINCIPAL_ROLE:service_admin",
    token_refresh_enabled=True,
    # S3 configuration for LocalStack
    s3_endpoint="http://localstack:4566",
    s3_region="us-east-1",
    s3_path_style_access=True,
    s3_access_key_id="test",
    s3_secret_access_key=SecretStr("test"),
)
catalog = create_catalog(config)
```

### Option 2: From CatalogProfile (Two-Tier Architecture)

```python
from floe_polaris import create_catalog
from floe_core.schemas import CatalogProfile, CredentialConfig, CredentialMode

profile = CatalogProfile(
    type="polaris",
    uri="http://polaris:8181/api/catalog",
    warehouse="demo_catalog",
    credentials=CredentialConfig(
        mode=CredentialMode.OAUTH2,
        scope="PRINCIPAL_ROLE:service_admin",
    ),
)
catalog = create_catalog(profile)
```

### Common Operations

```python
# List namespaces
namespaces = catalog.list_namespaces()

# Create namespace with parent hierarchy
catalog.create_namespace("demo.bronze", create_parents=True)

# Create namespace if not exists (idempotent)
catalog.create_namespace_if_not_exists("demo.silver")

# Load namespace info
ns_info = catalog.load_namespace("demo.bronze")
print(ns_info.properties)

# List tables in namespace
tables = catalog.list_tables("demo.bronze")

# Load table
table = catalog.load_table("demo.bronze.raw_events")

# Check if table exists
if catalog.table_exists("demo.bronze.raw_events"):
    table = catalog.load_table("demo.bronze.raw_events")
```

### Key Features

- **OAuth2 token refresh**: Automatic via PyIceberg's built-in mechanism
- **Circuit breaker**: Prevents cascading failures (configurable threshold)
- **Structured logging**: Via structlog with context
- **OpenTelemetry tracing**: Span tracking for all operations
- **Retry policies**: Exponential backoff with jitter

---

## dbt-duckdb Plugin Integration

### Location
`packages/floe-dbt/src/floe_dbt/plugins/polaris.py`

### Architecture (v2 - Native Writes)

**Plugin responsibilities**:
- ✅ Initialize PolarisCatalog for metadata operations
- ✅ `ATTACH` Polaris catalog to DuckDB (enables native writes)
- ❌ `store()` method REMOVED (DuckDB handles via `CREATE TABLE AS SELECT`)

### Plugin Implementation

```python
class Plugin(BasePlugin):
    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize Polaris catalog connection."""
        catalog_config = PolarisCatalogConfig(
            uri=config["catalog_uri"],
            warehouse=config["warehouse"],
            client_id=config.get("client_id"),
            client_secret=config.get("client_secret"),
            scope=config.get("scope", "PRINCIPAL_ROLE:ALL"),
            s3_endpoint=config.get("s3_endpoint"),
            s3_path_style_access=True,
        )
        self.catalog = PolarisCatalog(catalog_config)

    def configure_connection(self, conn: Any) -> None:
        """ATTACH Polaris catalog to DuckDB for native Iceberg writes."""
        attach_sql = f"""
        ATTACH IF NOT EXISTS '{self.config["warehouse"]}' AS polaris_catalog (
            TYPE ICEBERG,
            CLIENT_ID '{self.config["client_id"]}',
            CLIENT_SECRET '{self.config["client_secret"]}',
            OAUTH2_SERVER_URI '{self.config["catalog_uri"]}/v1/oauth/tokens',
            ENDPOINT '{self.config["catalog_uri"]}'
        )
        """
        conn.execute(attach_sql)
```

### Data Engineer Experience

**dbt model** (data engineer writes this):

```sql
-- models/gold/customer_metrics.sql
{{ config(
    materialized='table',
    schema='gold'
) }}

SELECT
    customer_id,
    SUM(order_amount) as total_spent,
    COUNT(*) as order_count
FROM {{ ref('silver_orders') }}
GROUP BY 1
```

**Platform transparently executes**:

```sql
CREATE TABLE polaris_catalog.demo.gold.customer_metrics AS
SELECT
    customer_id,
    SUM(order_amount) as total_spent,
    COUNT(*) as order_count
FROM polaris_catalog.demo.silver.silver_orders
GROUP BY 1
```

### profiles.yml Generation

The platform generates `profiles.yml` with plugin configuration:

```yaml
# Generated profiles.yml
demo:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: /tmp/floe.duckdb
      plugins:
        - module: floe_dbt.plugins.polaris
          alias: polaris
          config:
            catalog_uri: "{{ env_var('POLARIS_CATALOG_URI') }}"
            warehouse: "{{ env_var('POLARIS_WAREHOUSE') }}"
            client_id: "{{ env_var('POLARIS_CLIENT_ID') }}"
            client_secret: "{{ env_var('POLARIS_CLIENT_SECRET') }}"
            s3_endpoint: "{{ env_var('S3_ENDPOINT') }}"
            s3_region: "{{ env_var('S3_REGION', 'us-east-1') }}"
```

---

## Helm Chart Initialization

### Location
`demo/platform-config/charts/floe-infrastructure/templates/polaris-init-job.yaml`

### Purpose
Idempotent catalog, namespace, and role setup on Helm install/upgrade.

### Key Operations

#### 1. Wait for Polaris Readiness (Init Container)

```yaml
initContainers:
  - name: wait-for-polaris
    image: busybox:1.36
    command:
      - sh
      - -c
      - |
        until wget -q --spider http://polaris:8182/q/health/ready; do
          sleep 5
        done
```

#### 2. OAuth2 Token Acquisition

```python
def get_oauth_token():
    url = f"{POLARIS_URI}/api/catalog/v1/oauth/tokens"
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "PRINCIPAL_ROLE:ALL"
    }).encode()
    # ... (request handling)
```

#### 3. Catalog Creation (OpenAPI Spec - Flat Keys)

```python
storage_config = {
    "storageType": "S3",
    "allowedLocations": ["s3://iceberg-bronze/"],
    "endpoint": "http://localstack:4566",      # Flat key
    "pathStyleAccess": True,                    # Flat key (CRITICAL)
    "region": "us-east-1",
    "roleArn": "arn:aws:iam::000000000000:role/polaris-role"  # Optional
}

# Check if catalog exists
status, resp = api_request("GET", f"/api/management/v1/catalogs/{CATALOG_NAME}", token=token)
if status == 200:
    # Catalog exists - cannot update storage config (known limitation)
    print("Catalog exists, continuing with existing config")
elif status == 404:
    # Create new catalog
    api_request("POST", "/api/management/v1/catalogs", {
        "catalog": {
            "name": CATALOG_NAME,
            "type": "INTERNAL",
            "properties": {"default-base-location": STORAGE_LOCATION},
            "storageConfigInfo": storage_config
        }
    }, token)
```

#### 4. Hierarchical Namespace Creation

```python
# Extract parent namespaces (e.g., "demo" from "demo.bronze")
parents = set()
for ns in NAMESPACES:
    parts = ns.strip().split(".")
    if len(parts) > 1:
        parents.add(parts[0])

# Create parent namespaces FIRST
for parent in sorted(parents):
    api_request("POST", f"/api/catalog/v1/{CATALOG_NAME}/namespaces", {
        "namespace": [parent],
        "properties": {}
    }, token)

# Then create child namespaces
for ns in NAMESPACES:
    ns_parts = ns.strip().split(".")
    api_request("POST", f"/api/catalog/v1/{CATALOG_NAME}/namespaces", {
        "namespace": ns_parts,
        "properties": {}
    }, token)
```

#### 5. Catalog Role with Full Privileges

```python
# Create role
api_request("POST", f"/api/management/v1/catalogs/{CATALOG_NAME}/catalog-roles", {
    "catalogRole": {"name": "demo_data_admin"}
}, token)

# Grant privileges
privileges = [
    "CATALOG_MANAGE_CONTENT",
    "TABLE_CREATE", "TABLE_DROP", "TABLE_READ_DATA", "TABLE_WRITE_DATA",
    "NAMESPACE_CREATE", "NAMESPACE_DROP", "VIEW_CREATE", "VIEW_DROP"
]

for priv in privileges:
    api_request("PUT",
        f"/api/management/v1/catalogs/{CATALOG_NAME}/catalog-roles/demo_data_admin/grants",
        {"grant": {"type": "catalog", "privilege": priv}},
        token)
```

#### 6. Assign Catalog Role to Principal Role

```python
# Assign catalog role "demo_data_admin" to principal role "service_admin"
api_request("PUT",
    f"/api/management/v1/principal-roles/service_admin/catalog-roles/{CATALOG_NAME}",
    {"catalogRole": {"name": "demo_data_admin"}},
    token)
```

---

## Multi-Engine Access Patterns

### DuckDB Native Iceberg (floe-runtime default)

#### ATTACH Catalog

```sql
-- Plugin executes this automatically
ATTACH 'demo_catalog' AS polaris_catalog (
    TYPE ICEBERG,
    CLIENT_ID 'demo_client',
    CLIENT_SECRET 'demo_secret',
    OAUTH2_SERVER_URI 'http://polaris:8181/api/catalog/v1/oauth/tokens',
    ENDPOINT 'http://polaris:8181/api/catalog'
);
```

#### Query Operations

```sql
-- List all tables
SHOW ALL TABLES;

-- Query table
SELECT * FROM polaris_catalog.demo.bronze.raw_events LIMIT 100;

-- Time-travel by snapshot ID
SELECT * FROM polaris_catalog.demo.silver.clean_events
AT (VERSION => 1790528822676766947);

-- Time-travel by timestamp
SELECT * FROM polaris_catalog.demo.bronze.raw_events
AT (TIMESTAMP => TIMESTAMP '2025-01-15 10:00:00');

-- View snapshots
SELECT * FROM iceberg_snapshots(polaris_catalog.demo.bronze.raw_events);
```

#### Write Operations

```sql
-- Create table (dbt models use this pattern)
CREATE TABLE polaris_catalog.demo.gold.customer_metrics AS
SELECT customer_id, SUM(amount) as total
FROM polaris_catalog.demo.silver.orders
GROUP BY 1;

-- Insert data
INSERT INTO polaris_catalog.demo.bronze.events
VALUES (1, 'click', NOW()), (2, 'view', NOW());

-- Insert from query
INSERT INTO polaris_catalog.demo.silver.clean_events
SELECT * FROM read_parquet('s3://bucket/data/*.parquet');
```

#### DuckDB Limitations

- **UPDATE/DELETE**: Only on non-partitioned, non-sorted tables (v1.4.2+)
- **MERGE INTO**: Not yet supported
- **Schema evolution**: Not yet supported via DuckDB
- **Write mode**: Merge-on-read only (not copy-on-write)

### PyIceberg Direct (for advanced operations)

```python
from pyiceberg.catalog import load_catalog
import pyarrow as pa

catalog = load_catalog(
    "polaris",
    **{
        "type": "rest",
        "uri": "http://polaris:8181/api/catalog",
        "credential": "demo_client:demo_secret",
        "scope": "PRINCIPAL_ROLE:ALL",
        "warehouse": "demo_catalog",
        "token-refresh-enabled": "true",
    }
)

# Load table
table = catalog.load_table("demo.bronze.raw_events")

# Scan with filters
df = table.scan(
    row_filter="event_date >= '2025-01-01'",
    selected_fields=("event_id", "event_type", "event_date")
).to_pandas()

# Write PyArrow table
arrow_table = pa.Table.from_pandas(df)
table.overwrite(arrow_table)

# Append data
table.append(arrow_table)

# Schema evolution
with table.update_schema() as update:
    update.add_column("new_field", pa.string())

# Expire old snapshots
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=7)
table.expire_snapshots(older_than=cutoff)
```

### Dagster Integration (future)

**Not yet implemented in floe-runtime**, but planned using `dagster-iceberg` package:

```python
from dagster import Definitions, asset
from dagster_iceberg.config import IcebergCatalogConfig
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager
import pyarrow as pa

polaris_config = IcebergCatalogConfig(
    properties={
        "type": "rest",
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "demo_catalog",
        "credential": "demo_client:demo_secret",
        "scope": "PRINCIPAL_ROLE:ALL",
        "token-refresh-enabled": "true",
    }
)

io_manager = PyArrowIcebergIOManager(
    name="polaris_catalog",
    config=polaris_config,
    namespace="demo.bronze",
)

@asset(key_prefix=["bronze"])
def raw_events() -> pa.Table:
    """Asset stored as Iceberg table via Polaris catalog."""
    return pa.Table.from_pydict({"id": [1, 2, 3], "event": ["a", "b", "c"]})

@asset(key_prefix=["silver"])
def clean_events(raw_events: pa.Table) -> pa.Table:
    """Transformed asset in silver namespace."""
    return raw_events  # Apply transformations

defs = Definitions(
    assets=[raw_events, clean_events],
    resources={"io_manager": io_manager}
)
```

---

## Best Practices

### Security

- **Never log credentials**: Use `SecretStr` for all secrets
- **Least privilege scopes**: Use `PRINCIPAL_ROLE:<role_name>`, NOT `PRINCIPAL_ROLE:ALL`
- **Rotate credentials**: Via K8s secrets, not hardcoded values
- **Enable audit logging**: In production environments

### Configuration

- **Use two-tier architecture**: Credentials in `platform.yaml`, logical refs in `floe.yaml`
- **Enable token refresh**: `token_refresh_enabled: true`
- **Disable vended credentials for LocalStack**: `access_delegation: none`
- **Use path-style access**: `s3_path_style_access: true` for LocalStack/MinIO

### Namespace Organization

- **Medallion architecture**: `demo.bronze`, `demo.silver`, `demo.gold`
- **Create parents first**: Use `create_parents=True` or explicit hierarchy
- **Idempotent operations**: Use `create_namespace_if_not_exists()`

### Error Handling

- **Handle specific exceptions**: `NamespaceNotFoundError`, `CatalogConnectionError`
- **Retry with backoff**: Use circuit breaker pattern
- **Refresh metadata**: Call `table.refresh()` before critical operations
