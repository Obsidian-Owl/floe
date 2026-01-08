# ADR-0010: Multi-Compute Pipeline Architecture

## Status

Accepted (Revised)

## Context

Floe users need to run data transformations on various compute targets:

- **DuckDB** - Embedded analytics, cost-effective, production-ready
- **Snowflake** - Enterprise data warehouse
- **BigQuery** - Google Cloud analytics
- **Redshift** - AWS data warehouse
- **Databricks** - Unified analytics platform
- **Spark** - Distributed big data processing
- **PostgreSQL** - Operational analytics

A single pipeline may need **multiple compute engines** for different steps:
- Step 1: Spark cluster (process 10TB raw data)
- Step 2: DuckDB pod (build analytical metrics on 100GB result)

This is NOT about dev vs prod (environment drift). This is about **heterogeneous compute within a single pipeline**, where each step uses the SAME compute across all environments.

Options considered:
- **Single compute per platform** - Platform selects one, all pipelines inherit
- **Multi-compute with platform approval** - Platform approves N, data engineers select per-step (CHOSEN)
- **Unrestricted selection** - Data engineers can use any compute

## Decision

**Multi-compute with hierarchical governance.** Platform teams approve N compute targets; data engineers select per-transform from the approved list.

### Key Principles

1. **Platform approves, data engineers select** - Governance without bottlenecks
2. **Per-transform selection** - Different steps can use different compute engines
3. **Environment parity preserved** - Each step uses the SAME compute across dev/staging/prod
4. **Hierarchical inheritance** - Enterprise → Domain → Product (Data Mesh support)

### Environment Parity (No Drift)

```
Step 1: dev=Spark, staging=Spark, prod=Spark     ✓ No drift
Step 2: dev=DuckDB, staging=DuckDB, prod=DuckDB  ✓ No drift
```

What you test is what you deploy. Each transform uses the same compute across all environments.

## Consequences

### Positive

- **Flexible pipelines** - Use the right compute for each step
- **Cost optimization** - Heavy processing on Spark, analytics on DuckDB
- **Platform governance** - Only approved computes can be used
- **No environment drift** - Each step consistent across environments
- **Data Mesh ready** - Hierarchical governance (Enterprise → Domain → Product)

### Negative

- **More configuration** - Data engineers must specify compute (or use default)
- **Multiple dbt profiles** - Each compute needs profile configuration
- **Complexity** - Platform teams manage N compute configurations

### Neutral

- Connection credentials managed via secrets per compute
- dbt profiles.yml generated with multiple targets
- Compile-time validation ensures compute is in approved list

## Hierarchical Governance

### Central Platform (Non-Data Mesh)

```yaml
# manifest.yaml (Platform Team)
plugins:
  compute:
    approved:
      - name: duckdb
        config:
          threads: 8
          extensions: [httpfs, parquet]
      - name: spark
        config:
          cluster: spark-thrift.floe-platform.svc.cluster.local
      - name: snowflake
        config:
          warehouse: COMPUTE_WH
    default: duckdb  # Used when transform doesn't specify

# floe.yaml (Data Engineers)
platform:
  ref: oci://registry.example.com/floe-platform:v1.2.3

transforms:
  - type: dbt
    path: models/heavy_processing/
    compute: spark  # Select from approved list

  - type: dbt
    path: models/analytics/
    compute: duckdb  # Different compute for this step

  - type: dbt
    path: models/simple/
    # No compute specified → uses platform default (duckdb)
```

### Data Mesh (Enterprise → Domain → Product)

```yaml
# enterprise-manifest.yaml (Enterprise Team)
scope: enterprise
plugins:
  compute:
    approved: [duckdb, spark, snowflake, bigquery]
    default: duckdb

---
# sales-domain-manifest.yaml (Domain Team)
scope: domain
parent_manifest: oci://registry/enterprise-manifest:v1.0.0
plugins:
  compute:
    approved: [duckdb, spark]  # Subset of enterprise
    default: duckdb

---
# floe.yaml (Data Product)
platform:
  ref: oci://registry/sales-domain-manifest:v2.0.0

transforms:
  - type: dbt
    path: models/ingest/
    compute: spark  # Must be in domain's approved list

  - type: dbt
    path: models/mart/
    compute: duckdb
```

**Validation Rules:**
- Domain `approved` MUST be a subset of Enterprise `approved`
- Transform `compute` MUST be in effective `approved` list
- Compile-time error if validation fails

## CompiledArtifacts Pattern

```python
from pydantic import BaseModel

class ComputeConfig(BaseModel):
    """Configuration for a single compute target."""
    name: str                           # duckdb, spark, snowflake, etc.
    connection_secret_ref: str | None   # K8s secret reference
    properties: dict[str, Any]          # Target-specific config

class ComputeRegistry(BaseModel):
    """All approved compute configurations."""
    configs: dict[str, ComputeConfig]   # name → config
    default: str                        # Fallback when not specified

class TransformConfig(BaseModel):
    """Configuration for a single transform."""
    type: str                           # dbt, python, etc.
    path: str
    compute: str | None                 # Selected compute (None → default)
    # ... other fields

class CompiledArtifacts(BaseModel):
    """Contract between floe-core and consumers."""
    compute_registry: ComputeRegistry   # All approved computes
    transforms: list[TransformConfig]   # Each may specify compute
```

## Supported Targets

| Target | dbt Adapter | Use Case |
|--------|-------------|----------|
| DuckDB | dbt-duckdb | Embedded analytics, cost-effective |
| Snowflake | dbt-snowflake | Enterprise data warehouse |
| BigQuery | dbt-bigquery | Google Cloud analytics |
| Redshift | dbt-redshift | AWS data warehouse |
| Databricks | dbt-databricks | Unified analytics |
| Spark | dbt-spark | Distributed big data |
| PostgreSQL | dbt-postgres | Operational analytics |

## What Floe Does NOT Do

- ❌ Allow per-environment compute selection (prevents drift)
- ❌ Prescribe which targets are "appropriate" for specific use cases
- ❌ Optimize queries for specific targets (dbt handles this)
- ❌ Allow unapproved compute targets

## What Floe DOES Do

- ✅ Platform teams approve N compute targets
- ✅ Data engineers select compute per transform
- ✅ Validate compute is in approved list (compile-time)
- ✅ Generate dbt profiles for all approved computes
- ✅ Securely inject connection credentials
- ✅ Enforce environment parity (same compute per step across envs)
- ✅ Support hierarchical governance (Data Mesh)

## Example: Multi-Compute Pipeline

```yaml
# manifest.yaml (Platform Team)
plugins:
  compute:
    approved:
      - name: spark
        config:
          cluster: spark-thrift.floe-platform.svc.cluster.local
          port: 10001
      - name: duckdb
        config:
          threads: 8
          memory_limit: 4GB
    default: duckdb

# floe.yaml (Data Engineer)
name: sales-analytics
version: "1.0.0"

transforms:
  # Step 1: Heavy processing on Spark cluster
  - type: dbt
    path: models/staging/
    compute: spark
    tags: [heavy]

  # Step 2: Analytical metrics on DuckDB
  - type: dbt
    path: models/marts/
    compute: duckdb
    tags: [analytics]

  # Step 3: Simple transforms use default
  - type: dbt
    path: models/seeds/
    # compute: (uses default → duckdb)
```

This pipeline runs identically in dev, staging, and production:
- `models/staging/` always runs on Spark
- `models/marts/` always runs on DuckDB
- No environment drift

## ComputePlugin Interface

All compute plugins implement the `ComputePlugin` abstract base class:

```python
# floe_core/interfaces/compute.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ComputeConfig:
    """Configuration passed to compute plugins."""
    name: str                          # duckdb, snowflake, etc.
    connection_secret: str | None      # K8s secret reference
    properties: dict[str, Any] | None  # Target-specific properties

@dataclass
class ConnectionResult:
    """Result of connection validation."""
    success: bool
    message: str
    latency_ms: float | None

@dataclass
class ResourceSpec:
    """K8s resource requirements for dbt job pods."""
    cpu_request: str      # e.g., "500m"
    cpu_limit: str        # e.g., "2000m"
    memory_request: str   # e.g., "512Mi"
    memory_limit: str     # e.g., "2Gi"

class ComputePlugin(ABC):
    """Interface for compute engines where dbt transforms execute."""

    name: str               # e.g., "duckdb", "spark", "snowflake"
    version: str
    is_self_hosted: bool    # True for DuckDB/Spark, False for Snowflake/BigQuery

    @abstractmethod
    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        """Generate dbt profile.yml configuration for this compute target.

        Returns dict that becomes the target entry in profiles.yml.
        Uses dbt's env_var() for secrets - NEVER embed credentials.
        """
        pass

    @abstractmethod
    def get_required_dbt_packages(self) -> list[str]:
        """Return list of dbt packages/adapters required.

        e.g., ["dbt-duckdb>=1.7.0"] or ["dbt-spark>=1.7.0"]
        """
        pass

    @abstractmethod
    def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        """Test connection to compute engine.

        For cloud: verify credentials and permissions.
        For self-hosted: verify cluster is accessible.
        """
        pass

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for dbt job pods.

        workload_size: "small" | "medium" | "large"
        Returns CPU/memory requests/limits for the job pod.
        """
        pass
```

## Plugin Implementations

### DuckDB (Self-Hosted, Embedded)

```python
# plugins/floe-compute-duckdb/src/plugin.py
class DuckDBComputePlugin(ComputePlugin):
    name = "duckdb"
    version = "1.0.0"
    is_self_hosted = True  # Runs embedded in dbt pod

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "duckdb",
            "path": config.properties.get("path", "/data/warehouse.duckdb"),
            "threads": config.properties.get("threads", 4),
            "extensions": config.properties.get("extensions", ["httpfs", "parquet"]),
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-duckdb>=1.7.0"]

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        specs = {
            "small": ResourceSpec("500m", "1000m", "1Gi", "2Gi"),
            "medium": ResourceSpec("1000m", "2000m", "2Gi", "4Gi"),
            "large": ResourceSpec("2000m", "4000m", "4Gi", "8Gi"),
        }
        return specs.get(workload_size, specs["medium"])
```

### Spark (Self-Hosted, Distributed)

```python
# plugins/floe-compute-spark/src/plugin.py
class SparkComputePlugin(ComputePlugin):
    name = "spark"
    version = "1.0.0"
    is_self_hosted = True  # Requires Spark cluster deployment

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "spark",
            "method": "thrift",
            "host": config.properties.get("cluster", "spark-thrift.floe-platform.svc.cluster.local"),
            "port": config.properties.get("port", 10001),
            "schema": config.properties.get("schema", "default"),
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-spark>=1.7.0"]

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        # Spark runs on cluster, dbt pod only needs moderate resources
        return ResourceSpec("500m", "1000m", "512Mi", "1Gi")
```

### Snowflake (Cloud, Managed)

```python
# plugins/floe-compute-snowflake/src/plugin.py
class SnowflakeComputePlugin(ComputePlugin):
    name = "snowflake"
    version = "1.0.0"
    is_self_hosted = False  # Connects to cloud service

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "snowflake",
            "account": "{{ env_var('SNOWFLAKE_ACCOUNT') }}",
            "user": "{{ env_var('SNOWFLAKE_USER') }}",
            "password": "{{ env_var('SNOWFLAKE_PASSWORD') }}",
            "warehouse": config.properties.get("warehouse", "COMPUTE_WH"),
            "database": config.properties.get("database"),
            "schema": config.properties.get("schema", "PUBLIC"),
            "role": config.properties.get("role"),
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-snowflake>=1.7.0"]

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        # Snowflake runs remotely, pod only needs minimal resources
        return ResourceSpec("250m", "500m", "256Mi", "512Mi")
```

## References

- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md)
- [ADR-0008: Repository Split](0008-repository-split.md) - Plugin architecture
- [ADR-0038: Data Mesh Architecture](0038-data-mesh-architecture.md) - Hierarchical governance
- [dbt adapters](https://docs.getdbt.com/docs/available-adapters)
- [DuckDB production use cases](https://duckdb.org/why_duckdb)
