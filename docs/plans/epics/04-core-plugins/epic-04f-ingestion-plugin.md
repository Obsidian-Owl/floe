# Epic 4F: Ingestion Plugin

## Summary

The IngestionPlugin ABC defines the interface for data ingestion tools that load data from sources into the lakehouse. The default implementation uses dlt (data load tool) per ADR-0020, providing a Python-first, type-safe approach to building data pipelines.

**Key Insight**: Ingestion is the "I" in ELT - it loads raw data into Bronze layer Iceberg tables for subsequent dbt transformation.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [Epic 4F: Ingestion Plugin](https://linear.app/obsidianowl/project/epic-4f-ingestion-plugin-0547e9605dc7)

---

## Requirements Covered

| Requirement ID | Description | Priority | E2E Test |
|----------------|-------------|----------|----------|
| FR-050 | All 11 plugin types discoverable | CRITICAL | `test_all_plugin_types_discoverable` |
| REQ-090 | IngestionPlugin ABC definition | CRITICAL | - |
| REQ-091 | dlt integration | HIGH | - |
| REQ-092 | Source connector registry | HIGH | - |
| REQ-093 | Iceberg destination support | CRITICAL | - |
| REQ-094 | Incremental loading | HIGH | - |

---

## Architecture Alignment

### Target State (from Architecture Summary)

- **Ingestion is PLUGGABLE** - Platform team selects: dlt, Airbyte
- **dlt is the default** - Python-native, type-safe, Iceberg-native
- **IngestionPlugin** - Entry point `floe.ingestion`
- **Iceberg destination** - Direct write to Bronze layer tables

### Plugin Interface (from ADR-0020)

```python
class IngestionPlugin(PluginMetadata):
    """Abstract base class for data ingestion plugins."""

    @abstractmethod
    def list_available_sources(self) -> list[str]:
        """List available source connectors."""
        ...

    @abstractmethod
    def create_pipeline(
        self,
        source: str,
        destination: str,
        config: dict[str, Any],
    ) -> Any:
        """Create an ingestion pipeline."""
        ...

    @abstractmethod
    def run_pipeline(self, pipeline: Any) -> dict[str, Any]:
        """Execute ingestion pipeline, return summary."""
        ...

    @abstractmethod
    def get_dagster_asset_config(self, source: str) -> dict[str, Any]:
        """Generate Dagster asset configuration for this source."""
        ...
```

---

## File Ownership (Exclusive)

```text
# Core ABC
packages/floe-core/src/floe_core/plugins/
└── ingestion.py               # IngestionPlugin ABC

# dlt implementation
plugins/floe-ingestion-dlt/
├── src/floe_ingestion_dlt/
│   ├── __init__.py
│   ├── plugin.py              # DltIngestionPlugin
│   ├── sources/               # Source connector wrappers
│   │   ├── __init__.py
│   │   ├── sql_database.py
│   │   └── rest_api.py
│   ├── destinations/
│   │   └── iceberg.py         # Iceberg destination
│   └── dagster_assets.py      # Dagster asset factories
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml             # Entry point: floe.ingestion

# Test fixtures
testing/fixtures/ingestion.py
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 4C | Catalog for table registration |
| Blocked By | Epic 4D | Storage for data files |
| Blocks | Epic 5A | dbt transforms Bronze layer data |

---

## User Stories (for SpecKit)

### US1: IngestionPlugin ABC (P0)

**As a** plugin developer
**I want** a clear ABC for ingestion plugins
**So that** I can implement alternative ingestion tools (Airbyte)

**Acceptance Criteria**:
- [ ] `IngestionPlugin` ABC defined in floe-core
- [ ] `list_available_sources()` method defined
- [ ] `create_pipeline()` method defined
- [ ] `run_pipeline()` method defined
- [ ] Entry point `floe.ingestion` documented

### US2: dlt Plugin Implementation (P0)

**As a** data engineer
**I want** dlt as the default ingestion tool
**So that** I can load data from sources into Iceberg tables

**Acceptance Criteria**:
- [ ] `DltIngestionPlugin` implements ABC
- [ ] Registered as entry point `floe.ingestion`
- [ ] Sources available: `sql_database`, `rest_api`, `filesystem`
- [ ] Plugin discoverable via PluginRegistry

**Implementation**:
```python
# plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
from floe_core.plugins.ingestion import IngestionPlugin

class DltIngestionPlugin(IngestionPlugin):
    @property
    def name(self) -> str:
        return "dlt"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def list_available_sources(self) -> list[str]:
        return [
            "sql_database",
            "rest_api",
            "filesystem",
            "google_sheets",
            "stripe",
            "github",
        ]

    def create_pipeline(
        self,
        source: str,
        destination: str,
        config: dict[str, Any],
    ) -> dlt.Pipeline:
        """Create a dlt pipeline."""
        import dlt

        return dlt.pipeline(
            pipeline_name=config.get("name", f"{source}_to_{destination}"),
            destination=destination,
            dataset_name=config.get("dataset", "bronze"),
        )

    def run_pipeline(self, pipeline: Any) -> dict[str, Any]:
        """Execute dlt pipeline."""
        load_info = pipeline.run()
        return {
            "rows_loaded": load_info.metrics["rows"],
            "tables_loaded": list(load_info.dataset_name_to_tables.keys()),
            "execution_time_s": load_info.metrics["elapsed_time"],
        }

    def get_dagster_asset_config(self, source: str) -> dict[str, Any]:
        return {
            "source_type": source,
            "incremental_key": None,  # Set per-source
            "write_disposition": "append",
        }
```

### US3: Iceberg Destination (P1)

**As a** data engineer
**I want** dlt to write directly to Iceberg tables
**So that** Bronze layer data is immediately queryable

**Acceptance Criteria**:
- [ ] dlt Iceberg destination configured
- [ ] Uses CatalogPlugin for table registration
- [ ] Uses StoragePlugin for data files
- [ ] Schema evolution handled automatically

### US4: Dagster Asset Factories (P1)

**As a** data engineer
**I want** Dagster assets generated from dlt sources
**So that** ingestion is orchestrated alongside transforms

**Acceptance Criteria**:
- [ ] `@dlt_asset` decorator creates Dagster assets
- [ ] Assets appear in Dagster UI with lineage
- [ ] Incremental loading via partitions
- [ ] Error handling with retry logic

---

## Technical Notes

### Key Decisions

1. **dlt is default but pluggable** - Airbyte can be substituted
2. **Iceberg-native destination** - No intermediate staging
3. **Dagster integration** - dlt runs as Dagster assets
4. **Incremental by default** - Uses dlt's incremental loading

### dlt vs Airbyte Trade-offs

| Aspect | dlt | Airbyte |
|--------|-----|---------|
| Deployment | Python library | Separate service |
| Connectors | 30+ (growing) | 300+ |
| Iceberg support | Native | Requires custom dest |
| Python-first | Yes | No (YAML config) |
| Resource usage | Low | High (pods per sync) |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| dlt Iceberg dest maturity | MEDIUM | MEDIUM | Fallback to Parquet + external table |
| Source connector gaps | MEDIUM | LOW | Custom sources, REST API |
| Large data volumes | MEDIUM | MEDIUM | Chunking, incremental loading |

### Test Strategy

- **Unit**: `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py`
- **Contract**: `tests/contract/test_ingestion_abc.py`
- **Integration**: dlt loading to Iceberg via Polaris

---

## E2E Test Alignment

| Test | Current Status | After Epic |
|------|----------------|------------|
| `test_all_plugin_types_discoverable` | FAIL (INGESTION missing) | PASS |

---

## FloeSpec Ingestion Configuration

```yaml
# floe.yaml
ingestion:
  sources:
    - name: orders_api
      type: rest_api
      config:
        base_url: https://api.example.com/v1
        resources:
          - name: orders
            endpoint: /orders
            incremental:
              cursor_path: updated_at
      destination:
        table: bronze.raw_orders
        write_disposition: merge

    - name: postgres_customers
      type: sql_database
      config:
        connection_string: ${POSTGRES_URL}
        tables:
          - customers
          - products
      destination:
        schema: bronze
        write_disposition: replace
```

---

## SpecKit Context

### Relevant Codebase Paths
- `packages/floe-core/src/floe_core/plugins/`
- `plugins/` (new: floe-ingestion-dlt)
- `docs/architecture/plugin-system/`
- `docs/architecture/adr/0020-ingestion-plugins.md`

### Related Existing Code
- `PluginRegistry` from Epic 1
- `CatalogPlugin` from Epic 4C
- `StoragePlugin` from Epic 4D

### External Dependencies
- `dlt>=0.4.0`
- `dlt[iceberg]` (Iceberg destination)
- `pyiceberg>=0.5.0`
