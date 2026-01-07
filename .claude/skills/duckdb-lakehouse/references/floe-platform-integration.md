# floe-platform DuckDB Integration

## Architecture Overview

floe-platform uses DuckDB as the primary compute engine for data transformations, integrated with:
- **dbt**: SQL transforms with custom Polaris plugin
- **Dagster**: Orchestration with auto-discovered assets
- **Apache Iceberg**: Table format via Polaris catalog
- **Kubernetes**: Container-based deployment with resource management

```
┌─────────────────────────────────────────────────────────────┐
│                    Two-Tier Configuration                    │
│  floe.yaml (data engineer) + platform.yaml (platform eng)   │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              DbtProfilesGenerator (compile-time)             │
│  Generates profiles.yml from platform.yaml + env vars       │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│         Polaris Plugin (dbt-duckdb runtime)                  │
│  initialize() → PolarisCatalog for metadata                 │
│  configure_connection() → ATTACH with inline credentials    │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│           DuckDB Native Iceberg Writes                       │
│  CREATE TABLE polaris_catalog.schema.table AS SELECT ...    │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              Dagster Auto-Discovery                          │
│  Loads dbt manifest.json → Creates Dagster assets           │
└─────────────────────────────────────────────────────────────┘
```

## Container Lifecycle

### 1. Build-Time (Dockerfile)

```dockerfile
# docker/Dockerfile.demo
FROM python:3.10-slim

# Install Python packages
RUN pip install duckdb dbt-duckdb dagster dagster-dbt

# Copy application code
COPY demo/data_engineering /app/demo/data_engineering
COPY packages /app/packages

# Build-time dbt parse (generates manifest.json)
# This does NOT connect to database, just parses SQL
RUN cd /app/demo/data_engineering/dbt && dbt parse
```

### 2. Runtime Initialization (entrypoint.sh)

```bash
#!/bin/bash
# docker/entrypoint.sh

# Step 1: Pre-install DuckDB extensions
python3 << 'PYTHON_EOF'
import duckdb
db_path = '/tmp/floe.duckdb'
conn = duckdb.connect(db_path)
conn.execute("INSTALL iceberg")
conn.execute("INSTALL httpfs")
conn.close()
PYTHON_EOF

# Step 2: Generate dbt profiles.yml from platform.yaml
python3 << EOF
from pathlib import Path
from floe_core.compiler.dbt_profiles_generator import DbtProfilesGenerator

DbtProfilesGenerator.generate_from_env(
    floe_path=Path("/app/demo/data_engineering/floe.yaml"),
    output_path=Path("/app/demo/data_engineering/dbt/profiles.yml"),
    platform_file_env="FLOE_PLATFORM_FILE",
    profile_name="default",
)
EOF

# Step 3: Copy Dagster instance.yaml to writable location
mkdir -p "$DAGSTER_HOME"
cp /opt/dagster/instance/dagster.yaml "$DAGSTER_HOME/dagster.yaml"

# Step 4: Start Dagster gRPC code server
exec dagster api grpc --python-file /app/demo/data_engineering/orchestration/definitions.py
```

**Critical Decisions**:
- ✅ Use file-based database (`/tmp/floe.duckdb`) for extension persistence
- ✅ Pre-install extensions before dbt runs
- ❌ Skip `dbt compile` (triggers secret manager errors)
- ✅ Generate profiles.yml at runtime (uses environment-specific platform.yaml)

### 3. Execution (Dagster Run)

```python
# Dagster launches dbt run via DagsterDbtTranslator
# dbt-duckdb creates connection
# → Secret manager initializes (FIRST CONNECTION)
# → dbt-duckdb loads plugin from profiles.yml
# → Plugin.initialize() runs
# → Plugin.configure_connection() runs
#    → ATTACH with inline credentials (bypasses secret manager)
# → dbt executes models
#    → Uses custom table.sql materialization
#    → CREATE TABLE polaris_catalog.schema.table AS SELECT ...
```

## Inline Credentials Solution

### Problem: Secret Manager Timing

**Timeline**:
1. dbt-duckdb opens connection → Secret manager initializes
2. Plugin `configure_connection()` runs → **Too late to CREATE SECRET**
3. Any `CREATE SECRET` attempt → Error: "Secret Manager settings cannot be changed"

**Failed Approaches**:
- ❌ Create persistent secret in entrypoint (each dbt session has its own secret manager)
- ❌ Force secret loading with `SELECT COUNT(*) FROM duckdb_secrets()` (doesn't solve timing)
- ❌ Use `:memory:` database (extensions don't persist)

### Solution: Inline Credentials

```python
# packages/floe-dbt/src/floe_dbt/plugins/polaris.py

def configure_connection(self, conn: Any) -> None:
    """ATTACH Polaris catalog to DuckDB for native Iceberg writes.

    Uses inline OAuth2 credentials to avoid DuckDB secret manager initialization issues.
    The secret manager is already initialized when this method runs, preventing
    CREATE SECRET operations. Inline credentials bypass this limitation.
    """
    catalog_uri = self.config["catalog_uri"]
    warehouse = self.config["warehouse"]

    client_id = self.config.get("client_id") or os.getenv("POLARIS_CLIENT_ID")
    client_secret = self.config.get("client_secret") or os.getenv("POLARIS_CLIENT_SECRET")

    try:
        oauth2_server_uri = f"{catalog_uri}/v1/oauth/tokens"

        attach_sql = f"""
        ATTACH IF NOT EXISTS '{warehouse}' AS polaris_catalog (
            TYPE ICEBERG,
            CLIENT_ID '{client_id}',
            CLIENT_SECRET '{client_secret}',
            OAUTH2_SERVER_URI '{oauth2_server_uri}',
            ENDPOINT '{catalog_uri}'
        )
        """
        conn.execute(attach_sql)

    except Exception as e:
        import traceback
        traceback.print_exc()

        raise RuntimeError(
            f"Failed to ATTACH Polaris catalog '{warehouse}' at {catalog_uri}. "
            f"Error: {e}"
        ) from e
```

**Benefits**:
- ✅ Bypasses secret manager entirely
- ✅ Works with DuckDB 1.4+ Iceberg extension
- ✅ Environment variables from K8s secrets
- ✅ No persistent secrets (ephemeral per connection)

## Two-Tier Configuration Resolution

### Example: Polaris Catalog Configuration

**Input 1: floe.yaml** (data engineer never sees credentials):
```yaml
name: customer-analytics
catalog: default  # Logical reference
```

**Input 2: platform.yaml** (platform engineer manages infrastructure):
```yaml
catalogs:
  default:
    type: polaris
    uri: "http://floe-infra-polaris:8181/api/catalog"
    warehouse: demo_catalog
    credentials:
      mode: oauth2
      client_id:
        secret_ref: polaris-client-id
      client_secret:
        secret_ref: polaris-client-secret
      scope: "PRINCIPAL_ROLE:service_admin"
```

**Input 3: K8s Secrets**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: polaris-client-id
stringData:
  value: "principal_01234567-89ab-cdef-0123-456789abcdef"
---
apiVersion: v1
kind: Secret
metadata:
  name: polaris-client-secret
stringData:
  value: "secret_fedcba98-7654-3210-fedc-ba9876543210"
```

**Output: Generated profiles.yml**:
```yaml
default:
  outputs:
    dev:
      type: duckdb
      path: "/tmp/floe.duckdb"
      plugins:
        - module: floe_dbt.plugins.polaris
          config:
            catalog_uri: "{{ env_var('FLOE_POLARIS_URI') }}"
            warehouse: "{{ env_var('FLOE_POLARIS_WAREHOUSE') }}"
            client_id: "{{ env_var('POLARIS_CLIENT_ID') }}"
            client_secret: "{{ env_var('POLARIS_CLIENT_SECRET') }}"
            scope: "PRINCIPAL_ROLE:service_admin"
```

**Environment Variables (Injected by K8s)**:
```bash
FLOE_POLARIS_URI=http://floe-infra-polaris:8181/api/catalog
FLOE_POLARIS_WAREHOUSE=demo_catalog
POLARIS_CLIENT_ID=${POLARIS_CLIENT_ID}      # From K8s secret
POLARIS_CLIENT_SECRET=${POLARIS_CLIENT_SECRET}  # From K8s secret
```

## Dagster Integration

### Asset Auto-Discovery

```python
# demo/data_engineering/orchestration/definitions.py
from dagster import Definitions
from dagster_dbt import DbtCliResource, load_assets_from_dbt_project

DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt"

dbt_assets = load_assets_from_dbt_project(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    key_prefix=["dbt"],
)

defs = Definitions(
    assets=dbt_assets,
    resources={
        "dbt": DbtCliResource(
            project_dir=str(DBT_PROJECT_DIR),
            profiles_dir=str(DBT_PROJECT_DIR),
        )
    }
)
```

**Key Points**:
- Dagster reads `dbt/target/manifest.json` (generated by `dbt parse` at build time)
- No database connection needed for discovery
- Actual execution runs `dbt run` which triggers plugin initialization

### Resource Management (K8s)

```yaml
# demo/platform-config/platform/local/platform.yaml
infrastructure:
  resource_profiles:
    transform:
      requests:
        cpu: "1000m"       # 1 core guaranteed
        memory: "4Gi"      # 4Gi guaranteed
      limits:
        cpu: "8000m"       # 8 cores burstable
        memory: "12Gi"     # 12Gi max
      env:
        DUCKDB_MEMORY_LIMIT: "8GB"  # 67% of 12Gi limit
        DUCKDB_THREADS: "4"
        DUCKDB_TEMP_DIRECTORY: "/tmp/duckdb"
```

**Rationale**:
- DuckDB + PyArrow + dbt require ~12Gi for data processing workloads
- Allows 1-2 concurrent transform jobs within 24GB OrbStack budget
- Conservative thread count (4) prevents CPU saturation

## Common Errors and Solutions

### Error 1: "Secret Manager settings cannot be changed"

**Symptom**:
```
Invalid Input Error: Changing Secret Manager settings after the secret manager is used is not allowed!
```

**Root Cause**: Attempting `CREATE SECRET` after secret manager initialization.

**Solution**: Use inline credentials in ATTACH statement (see `configure_connection()` above).

### Error 2: "ICEBERG extension not found"

**Symptom**:
```
Catalog Error: Type with name iceberg does not exist!
```

**Root Cause**: Extensions not pre-installed or using `:memory:` database.

**Solution**: Pre-install in entrypoint with file-based database (`/tmp/floe.duckdb`).

### Error 3: "No ICEBERG secret by the name of 'polaris_secret'"

**Symptom**:
```
BinderException: No ICEBERG secret by the name of 'polaris_secret' could be found
```

**Root Cause**: DuckDB Issue #18021 - persistent secrets not automatically loaded.

**Solution**: Use inline credentials (no secret creation needed).

### Error 4: "NotFoundException: Unable to find warehouse demo_catalog"

**Symptom**: ATTACH succeeds but queries fail.

**Root Cause**: Polaris warehouse not created via REST API.

**Solution**: Create warehouse using Polaris REST API or UI before ATTACH.

## Best Practices

### DO ✅

- ✅ Use file-based database (`/tmp/floe.duckdb`) for extension persistence
- ✅ Pre-install extensions in entrypoint before dbt runs
- ✅ Use inline credentials in ATTACH statement
- ✅ Generate profiles.yml at runtime from platform.yaml
- ✅ Use environment variables from K8s secrets
- ✅ Set DUCKDB_MEMORY_LIMIT to 67% of container memory limit
- ✅ Use `dbt parse` at build time (no DB connection)
- ✅ Use `dbt run` at runtime (actual execution)

### DON'T ❌

- ❌ Use `:memory:` database (extensions don't persist)
- ❌ Run `dbt compile` in entrypoint (triggers secret manager errors)
- ❌ Use `CREATE SECRET` in plugin (too late, secret manager locked)
- ❌ Hardcode credentials (use env vars from K8s secrets)
- ❌ Share DuckDB connections across threads
- ❌ Bypass ATTACH for direct S3 writes (loses catalog coordination)
- ❌ Use multiple writers to same DuckDB file (single-writer limitation)

## References

- DuckDB 1.4.3 Iceberg Extension: packages/floe-dbt/src/floe_dbt/plugins/polaris.py
- DbtProfilesGenerator: packages/floe-core/src/floe_core/compiler/dbt_profiles_generator.py
- Container Entrypoint: docker/entrypoint.sh
- Platform Configuration: demo/platform-config/platform/local/platform.yaml
- Dagster Definitions: demo/data_engineering/orchestration/definitions.py
