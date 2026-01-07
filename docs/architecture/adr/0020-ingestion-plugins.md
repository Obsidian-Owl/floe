# ADR-0020: Ingestion Plugins

## Status

Accepted

## Context

Data pipelines need to ingest data from external sources (APIs, databases, SaaS applications) before transformation. floe needs an ingestion strategy that:

1. Integrates with the orchestration layer (Dagster/Airflow)
2. Writes to Iceberg tables (enforced format)
3. Provides a plugin model for different ingestion tools
4. Supports both embedded and external ingestion systems

### Options Considered

| Tool | Pros | Cons |
|------|------|------|
| **dlt** | Python-native, lightweight, Dagster-native, 60+ connectors | Smaller ecosystem than Airbyte |
| **Airbyte** | 600+ connectors, enterprise-grade, UI | 11+ services required, heavy |
| **Singer/Meltano** | Simple protocol | Abandoned by Talend, fragmented |
| **Fivetran** | Managed, reliable | Proprietary, expensive |
| **Custom** | Full control | Huge effort, reinvents wheel |

## Decision

Adopt a **two-tier ingestion strategy**:

1. **dlt (default)** - Embedded, Python-native, Dagster-native
2. **Airbyte (external)** - For organizations with existing Airbyte deployments

### Default: dlt (data load tool)

dlt is the recommended ingestion framework because:

- **Python-native**: Runs in the same environment as dbt and Dagster
- **Lightweight**: No additional services required
- **Dagster-native**: First-class integration with Dagster assets
- **60+ connectors**: REST APIs, databases, SaaS apps
- **Iceberg support**: Native dlt destination for Iceberg

### External: Airbyte

For organizations with existing Airbyte deployments:

- **Connect only**: floe connects to external Airbyte
- **No deployment**: Airbyte must be deployed separately
- **Trigger syncs**: Via Airbyte API

## Consequences

### Positive

- **Batteries included** - dlt works out of the box
- **Flexibility** - Organizations can use existing Airbyte
- **Python ecosystem** - dlt integrates naturally with Dagster
- **No heavy infrastructure** - dlt doesn't require 11+ services

### Negative

- **Fewer connectors** - dlt has ~60 vs Airbyte's 600+
- **Less mature** - dlt is newer than Airbyte
- **Custom connectors** - May need to write dlt sources

### Neutral

- Organizations with existing Airbyte continue using it
- dlt connectors are growing rapidly
- Both write to Iceberg (enforced format)

## IngestionPlugin Interface

```python
# floe_core/interfaces/ingestion.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class IngestionConfig:
    """Configuration for an ingestion pipeline."""
    name: str                           # Pipeline name
    source: str                         # Source identifier
    destination_table: str              # Target Iceberg table
    write_disposition: str              # append | replace | merge
    incremental: dict | None            # Incremental config
    secret_refs: dict[str, str] | None  # Secret references

@dataclass
class IngestionResult:
    """Result of an ingestion run."""
    success: bool
    rows_loaded: int
    tables_created: list[str]
    duration_seconds: float
    error: str | None

class IngestionPlugin(ABC):
    """Interface for data ingestion/EL plugins."""

    name: str                # e.g., "dlt", "airbyte"
    version: str
    is_external: bool        # True for Airbyte (external service)

    @abstractmethod
    def create_pipeline(self, config: IngestionConfig) -> any:
        """Create ingestion pipeline from configuration.

        For dlt: creates a dlt pipeline object
        For Airbyte: returns connection configuration
        """
        pass

    @abstractmethod
    def run(self, pipeline: any, **kwargs) -> IngestionResult:
        """Execute the ingestion pipeline.

        For dlt: runs the pipeline directly
        For Airbyte: triggers sync via API
        """
        pass

    @abstractmethod
    def get_destination_config(self, catalog_config: dict) -> dict:
        """Generate destination configuration for writing to Iceberg.

        All ingestion plugins MUST write to Iceberg tables via the catalog.
        """
        pass

    @abstractmethod
    def create_dagster_assets(self, configs: list[IngestionConfig]) -> list:
        """Create Dagster assets from ingestion configurations."""
        pass
```

## Plugin Implementations

### dlt Plugin (Default)

```python
# plugins/floe-ingestion-dlt/src/plugin.py
import dlt
from floe_core.interfaces.ingestion import IngestionPlugin, IngestionConfig, IngestionResult

class DltIngestionPlugin(IngestionPlugin):
    name = "dlt"
    version = "1.0.0"
    is_external = False  # Runs embedded

    def create_pipeline(self, config: IngestionConfig) -> dlt.Pipeline:
        return dlt.pipeline(
            pipeline_name=config.name,
            destination="filesystem",  # Write to Iceberg via filesystem
            dataset_name=config.destination_table.split(".")[0],
        )

    def run(self, pipeline: dlt.Pipeline, source: any) -> IngestionResult:
        info = pipeline.run(source)
        return IngestionResult(
            success=not info.has_failed_jobs,
            rows_loaded=info.metrics.get("rows_processed", 0),
            tables_created=[t.name for t in info.load_packages[0].tables],
            duration_seconds=info.metrics.get("duration", 0),
            error=str(info.exception) if info.has_failed_jobs else None,
        )

    def get_destination_config(self, catalog_config: dict) -> dict:
        return {
            "filesystem": {
                "bucket_url": catalog_config["warehouse_path"],
                "credentials": catalog_config["credentials"],
            },
            "table_format": "iceberg",
        }

    def create_dagster_assets(self, configs: list[IngestionConfig]) -> list:
        from dagster_embedded_elt.dlt import DagsterDltResource, dlt_assets
        # Returns Dagster assets for each ingestion config
        ...
```

### Airbyte Plugin (External)

```python
# plugins/floe-ingestion-airbyte/src/plugin.py
import requests
from floe_core.interfaces.ingestion import IngestionPlugin, IngestionConfig, IngestionResult

class AirbyteIngestionPlugin(IngestionPlugin):
    name = "airbyte"
    version = "1.0.0"
    is_external = True  # Connects to external Airbyte

    def __init__(self, workspace_url: str, api_token: str):
        self.workspace_url = workspace_url
        self.api_token = api_token

    def create_pipeline(self, config: IngestionConfig) -> dict:
        # Returns Airbyte connection ID
        return {
            "connection_id": config.source,
            "workspace_url": self.workspace_url,
        }

    def run(self, pipeline: dict, **kwargs) -> IngestionResult:
        # Trigger Airbyte sync via API
        response = requests.post(
            f"{pipeline['workspace_url']}/api/v1/connections/sync",
            headers={"Authorization": f"Bearer {self.api_token}"},
            json={"connectionId": pipeline["connection_id"]},
        )
        # Wait for completion, return result
        ...

    def get_destination_config(self, catalog_config: dict) -> dict:
        # Airbyte destination must be configured separately
        return {
            "destination_type": "iceberg",
            "iceberg_catalog": catalog_config["catalog_uri"],
        }
```

## Configuration

### Platform Manifest

```yaml
# platform-manifest.yaml
plugins:
  ingestion:
    type: dlt  # Default: dlt
    # OR
    type: airbyte
    config:
      workspace_url: https://airbyte.example.com
      connection_secret_ref: airbyte-api-token
```

### Pipeline Configuration

```yaml
# floe.yaml
ingestion:
  # dlt source
  - name: github_events
    type: dlt
    destination: bronze.github_events
    dlt:
      source: dlt.sources.github.github_reactions
      resource: issues
      write_disposition: merge
      incremental:
        cursor_column: updated_at
    secret_refs:
      github_token: github-api-token

  # External Airbyte connection
  - name: salesforce_sync
    type: airbyte
    destination: bronze.salesforce_accounts
    airbyte:
      connection_id: "abc123-def456"
```

## Integration with Dagster

### dlt Assets

```python
# Generated by floe compile
from dagster import asset, AssetExecutionContext
from dagster_embedded_elt.dlt import DagsterDltResource

@asset(
    name="bronze_github_events",
    group_name="ingestion",
    compute_kind="dlt",
)
def github_events_asset(context: AssetExecutionContext, dlt: DagsterDltResource):
    yield from dlt.run(
        source=github_reactions(access_token=context.op_config["github_token"]),
        destination="iceberg",
    )
```

### Airbyte Assets

```python
# Generated by floe compile
from dagster import asset, AssetExecutionContext
from dagster_airbyte import AirbyteResource

@asset(
    name="bronze_salesforce_accounts",
    group_name="ingestion",
    compute_kind="airbyte",
)
def salesforce_asset(context: AssetExecutionContext, airbyte: AirbyteResource):
    airbyte.sync_and_poll(connection_id="abc123-def456")
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL SOURCES                                                        │
│                                                                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │  GitHub   │  │ Salesforce│  │  Postgres │  │  REST API │            │
│  │    API    │  │    API    │  │    DB     │  │           │            │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘            │
│        │              │              │              │                    │
└────────│──────────────│──────────────│──────────────│────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER                                                         │
│                                                                          │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐  │
│  │  dlt (default)                 │  │  Airbyte (external)           │  │
│  │                                │  │                                │  │
│  │  • Python-native               │  │  • 600+ connectors            │  │
│  │  • Runs in K8s Job             │  │  • External deployment        │  │
│  │  • Dagster-native              │  │  • API integration            │  │
│  │  • 60+ connectors              │  │                                │  │
│  └───────────────┬───────────────┘  └───────────────┬───────────────┘  │
│                  │                                   │                   │
└──────────────────│───────────────────────────────────│───────────────────┘
                   │                                   │
                   ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ICEBERG TABLES (bronze layer)                                           │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │bronze.github    │  │bronze.salesforce│  │bronze.postgres  │         │
│  │_events          │  │_accounts        │  │_orders          │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Error Handling

Ingestion plugins follow the error taxonomy defined in [ADR-0025: Plugin Error Taxonomy](0025-plugin-error-taxonomy.md).

### Error Categories

| Category | Description | Retry | Example |
|----------|-------------|-------|---------|
| `TRANSIENT` | Temporary failures, safe to retry | Yes | API rate limit, network timeout |
| `PERMANENT` | Unrecoverable, do not retry | No | Invalid credentials, missing table |
| `PARTIAL` | Some records failed | Configurable | Schema mismatch on subset of rows |
| `CONFIGURATION` | Plugin misconfiguration | No | Invalid source connector settings |

### Error Response Format

```python
@dataclass
class IngestionError:
    """Structured error from ingestion plugin."""
    category: Literal["TRANSIENT", "PERMANENT", "PARTIAL", "CONFIGURATION"]
    code: str           # e.g., "RATE_LIMITED", "AUTH_FAILED", "SCHEMA_MISMATCH"
    message: str        # Human-readable message
    source: str         # Source system (e.g., "github", "salesforce")
    retryable: bool
    retry_after_seconds: int | None  # For TRANSIENT errors
    failed_records: int | None       # For PARTIAL errors
    details: dict | None             # Additional context

# Example usage in IngestionResult
@dataclass
class IngestionResult:
    success: bool
    rows_loaded: int
    tables_created: list[str]
    duration_seconds: float
    error: IngestionError | None  # Structured error instead of string
```

### dlt Error Mapping

| dlt Exception | Category | Code |
|---------------|----------|------|
| `ResourceNotFound` | PERMANENT | `SOURCE_NOT_FOUND` |
| `CredentialsRequired` | PERMANENT | `AUTH_FAILED` |
| `LoadClientError` | CONFIGURATION | `DESTINATION_CONFIG_ERROR` |
| `RetryException` | TRANSIENT | `RATE_LIMITED` |
| `SchemaCorruptedException` | PERMANENT | `SCHEMA_CORRUPTION` |
| `PipelineStepFailed` (partial) | PARTIAL | `PARTIAL_LOAD` |

### Airbyte Error Mapping

| Airbyte Status | Category | Code |
|----------------|----------|------|
| `FAILED` (auth) | PERMANENT | `AUTH_FAILED` |
| `FAILED` (rate limit) | TRANSIENT | `RATE_LIMITED` |
| `INCOMPLETE` | PARTIAL | `PARTIAL_SYNC` |
| `CANCELLED` | PERMANENT | `SYNC_CANCELLED` |

### Retry Configuration

```yaml
# platform-manifest.yaml
plugins:
  ingestion:
    type: dlt
    retry:
      max_attempts: 3
      initial_delay_seconds: 60
      max_delay_seconds: 3600
      backoff_multiplier: 2.0
      retryable_categories: [TRANSIENT]
```

### Observability

Ingestion errors emit OpenLineage events and metrics:

```json
{
  "eventType": "FAIL",
  "job": { "name": "ingestion.github_events" },
  "run": {
    "facets": {
      "errorMessage": {
        "message": "GitHub API rate limit exceeded",
        "programmingLanguage": "python",
        "stackTrace": "..."
      },
      "ingestionError": {
        "category": "TRANSIENT",
        "code": "RATE_LIMITED",
        "retryAfterSeconds": 3600
      }
    }
  }
}
```

**Prometheus Metrics:**

| Metric | Type | Labels |
|--------|------|--------|
| `floe_ingestion_errors_total` | Counter | source, category, code |
| `floe_ingestion_retry_total` | Counter | source |
| `floe_ingestion_rows_failed_total` | Counter | source |

### Testing Custom Plugins

Custom ingestion plugins should include error handling tests:

```python
# tests/test_my_source_plugin.py
import pytest
from my_plugin import MyIngestionPlugin
from floe_core.interfaces.ingestion import IngestionError

class TestMyIngestionPluginErrors:

    def test_auth_failure_returns_permanent_error(self, mock_source):
        mock_source.raise_auth_error()
        plugin = MyIngestionPlugin()

        result = plugin.run(pipeline, source=mock_source)

        assert result.success is False
        assert result.error.category == "PERMANENT"
        assert result.error.code == "AUTH_FAILED"
        assert result.error.retryable is False

    def test_rate_limit_returns_transient_error(self, mock_source):
        mock_source.raise_rate_limit(retry_after=60)
        plugin = MyIngestionPlugin()

        result = plugin.run(pipeline, source=mock_source)

        assert result.success is False
        assert result.error.category == "TRANSIENT"
        assert result.error.retryable is True
        assert result.error.retry_after_seconds == 60
```

## References

- [dlt Documentation](https://dlthub.com/docs)
- [Airbyte API](https://reference.airbyte.com/)
- [dagster-embedded-elt](https://docs.dagster.io/integrations/embedded-elt/dlt)
- [ADR-0008: Repository Split](0008-repository-split.md) - Plugin architecture
- [ADR-0018: Opinionation Boundaries](0018-opinionation-boundaries.md) - Pluggable components
- [ADR-0025: Plugin Error Taxonomy](0025-plugin-error-taxonomy.md) - Error classification
