# ADR-0010: Target-Agnostic Compute

## Status

Accepted

## Context

Floe users need to run data transformations on various compute targets:

- **DuckDB** - Local development, small datasets, cost-effective production
- **Snowflake** - Enterprise data warehouse
- **BigQuery** - Google Cloud analytics
- **Redshift** - AWS data warehouse
- **Databricks** - Unified analytics platform
- **PostgreSQL** - Operational analytics

We need to decide how Floe handles compute target selection.

Options considered:
- **Floe prescribes targets** - dev=DuckDB, prod=Snowflake
- **User chooses target** - Floe is agnostic
- **Per-environment targets** - Different targets per environment type

## Decision

**Floe is target-agnostic.** Users choose their compute target; Floe passes configuration through to dbt.

## Consequences

### Positive

- **User flexibility** - DuckDB can be production for some use cases
- **No lock-in** - Users choose based on their needs
- **Simpler Floe** - Don't need to understand target specifics
- **dbt handles details** - Dialect translation via dbt adapters
- **Cost optimization** - Users can choose cost-appropriate targets

### Negative

- **More user configuration** - Users must specify target
- **No opinionated defaults** - Might be harder for beginners
- **Testing complexity** - Need to test with multiple targets

### Neutral

- Connection credentials managed via secrets
- Target configuration in floe.yaml
- dbt profiles.yml generated from config

## Configuration Pattern

Compute target is set ONCE at the **platform level**, not per-environment. This prevents drift between dev/staging/prod.

```yaml
# platform-manifest.yaml (Platform Team)
plugins:
  compute:
    type: duckdb  # Set ONCE, inherited by all pipelines

# floe.yaml (Data Team)
# NOTE: Data engineers do NOT select compute target - they inherit it
platform:
  ref: oci://registry.example.com/floe-platform:v1.2.3

transforms:
  - type: dbt
    path: models/
```

**Key Decision**: Same compute across all environments. DuckDB is a viable production choice.

## CompiledArtifacts Pattern

```go
// User specifies target, Floe passes through
type ComputeConfig struct {
    // Target type chosen by user
    Target string `json:"target"`  // duckdb, snowflake, bigquery, etc.

    // Connection reference (resolved from secrets)
    ConnectionSecret string `json:"connection_secret,omitempty"`

    // Target-specific properties (passed to dbt profiles.yml)
    Properties map[string]any `json:"properties,omitempty"`
}
```

## Supported Targets

| Target | dbt Adapter | Notes |
|--------|-------------|-------|
| DuckDB | dbt-duckdb | Local, serverless, embedded |
| Snowflake | dbt-snowflake | Enterprise DW |
| BigQuery | dbt-bigquery | Google Cloud |
| Redshift | dbt-redshift | AWS |
| Databricks | dbt-databricks | Unified analytics |
| PostgreSQL | dbt-postgres | Operational |
| Spark | dbt-spark | Big data |

## What Floe Does NOT Do

- ❌ Allow per-environment compute targets (prevents drift)
- ❌ Prescribe which targets are "appropriate" for production
- ❌ Optimize queries for specific targets
- ❌ Manage target-specific connection pooling

## What Floe DOES Do

- ✅ Pass target configuration to dbt
- ✅ Securely inject connection credentials
- ✅ Provision supporting infrastructure (if applicable)
- ✅ Collect target-agnostic observability

## Example: DuckDB in Production

Valid configuration - Platform Team chooses DuckDB for all environments:

```yaml
# platform-manifest.yaml
plugins:
  compute:
    type: duckdb
    config:
      path: s3://bucket/warehouse.duckdb
      memory_limit: 4GB
```

This configuration applies to dev, staging, and production - no environment drift.

## ComputePlugin Interface

All compute plugins implement the `ComputePlugin` abstract base class:

```python
# floe_core/interfaces/compute.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ComputeConfig:
    """Configuration passed to compute plugins."""
    target: str                        # duckdb, snowflake, etc.
    connection_secret: str | None      # K8s secret reference
    properties: dict[str, any] | None  # Target-specific properties

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
            "host": "spark-thrift.floe-platform.svc.cluster.local",
            "port": 10001,
            "schema": config.properties.get("schema", "default"),
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-spark>=1.7.0"]
```

## Compute Plugin Selection

Platform Team selects compute ONCE in `platform-manifest.yaml`:

```yaml
plugins:
  compute:
    type: duckdb  # or spark, snowflake, databricks, bigquery
    config:
      threads: 8
      path: s3://bucket/warehouse.duckdb
```

This selection is inherited by all pipelines. Data engineers do NOT select compute.

## References

- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md)
- [ADR-0008: Repository Split](0008-repository-split.md) - Plugin architecture
- [dbt adapters](https://docs.getdbt.com/docs/available-adapters)
- [DuckDB production use cases](https://duckdb.org/why_duckdb)
