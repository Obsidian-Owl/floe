# ComputePlugin

**Purpose**: Define where dbt transforms execute (compute engines)
**Location**: `floe_core/interfaces/compute.py`
**Entry Point**: `floe.computes`
**ADR**: [ADR-0010: Target-Agnostic Compute](../adr/0010-target-agnostic-compute.md)

ComputePlugin abstracts the execution environment for dbt transformations. This enables platform teams to select compute engines (DuckDB, Snowflake, Spark, BigQuery) based on cost, performance, and organizational requirements while maintaining consistent dbt model definitions.

## Interface Definition

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

        Example return:
            {
                "type": "snowflake",
                "account": "{{ env_var('SNOWFLAKE_ACCOUNT') }}",
                "user": "{{ env_var('SNOWFLAKE_USER') }}",
                "password": "{{ env_var('SNOWFLAKE_PASSWORD') }}",
                "warehouse": "COMPUTE_WH",
            }
        """
        pass

    @abstractmethod
    def get_required_dbt_packages(self) -> list[str]:
        """Return list of dbt packages/adapters required.

        Example: ["dbt-duckdb>=1.7.0"] or ["dbt-spark>=1.7.0"]
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

        Args:
            workload_size: "small" | "medium" | "large"

        Returns:
            ResourceSpec with CPU/memory requests/limits for the job pod.
        """
        pass

    def get_catalog_attachment_sql(
        self,
        catalog_config: "CatalogConfig"
    ) -> list[str] | None:
        """Return SQL statements to attach compute engine to Iceberg catalog.

        For DuckDB: Returns ATTACH statements for Iceberg REST catalog
        For Spark: Returns None (uses SparkCatalog configuration)
        For Snowflake: Returns None (uses external volume config)

        This method enables compute engines to connect to the catalog
        before dbt models execute, ensuring all table operations go
        through the catalog's metadata management.

        Args:
            catalog_config: Configuration for the Iceberg catalog

        Returns:
            List of SQL statements to execute as dbt pre-hooks,
            or None if compute engine doesn't need explicit attachment.

        Example (DuckDB):
            [
                "LOAD iceberg;",
                "CREATE SECRET IF NOT EXISTS polaris_secret (...);",
                "ATTACH IF NOT EXISTS 'warehouse' AS ice (TYPE iceberg, ...);"
            ]
        """
        return None  # Default: no attachment needed
```

## Reference Implementations

| Plugin | Description | Self-Hosted |
|--------|-------------|-------------|
| `DuckDBComputePlugin` | In-process analytical database | Yes |
| `SnowflakeComputePlugin` | Cloud data warehouse | No |
| `SparkComputePlugin` | Distributed compute cluster | Yes |
| `BigQueryComputePlugin` | Google Cloud warehouse | No |
| `DatabricksComputePlugin` | Unified analytics platform | No |

## Related Documents

- [ADR-0010: Target-Agnostic Compute](../adr/0010-target-agnostic-compute.md)
- [Plugin Architecture](../plugin-architecture.md)
- [CatalogPlugin](catalog-plugin.md) - For catalog attachment
