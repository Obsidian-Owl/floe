# Epic 4G: Reverse ETL (SinkConnector)

## Summary

The SinkConnector mixin extends the IngestionPlugin interface to support reverse ETL — pushing data from the lakehouse (Iceberg Gold layer) back to external SaaS APIs, databases, and services. The default implementation uses dlt's `@dlt.destination` decorator, leveraging the same dlt framework used for ingestion (Epic 4F).

**Key Insight**: Reverse ETL is the "L" in reverse — it loads curated data OUT of the lakehouse into operational systems. The industry is converging toward unified data movement (Fivetran acquired Census for this reason). dlt treats reverse ETL as the same framework, different direction.

**Architectural Decision**: SinkConnector is an opt-in ABC mixin (not a new plugin type). Plugins that support both ingestion and egress implement both `IngestionPlugin` and `SinkConnector`. This was decided during Epic 4F research (Option C, scored 8.2/10) because it requires zero breaking changes to existing code, schemas, or plugin count.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [Epic 4G: Reverse ETL (SinkConnector)](https://linear.app/obsidianowl/project/epic-4g-reverse-etl-sinkconnector-b69dd02b131d)

---

## Requirements Covered

| Requirement ID | Description | Priority | E2E Test |
|----------------|-------------|----------|----------|
| REQ-095 | SinkConnector ABC definition | HIGH | - |
| REQ-096 | dlt reverse ETL via `@dlt.destination` | HIGH | - |
| REQ-097 | SaaS destination connectors | MEDIUM | - |
| REQ-098 | Capability detection via `isinstance(plugin, SinkConnector)` | HIGH | - |
| REQ-099 | Egress configuration in floe.yaml | MEDIUM | - |

---

## Architecture Alignment

### Target State (from Architecture Summary + Epic 4F Research)

- **SinkConnector is an opt-in mixin** — not a 12th plugin type
- **Plugin count stays at 11** — PluginType enum unchanged
- **CompiledArtifacts unchanged** — no schema changes required
- **floe.yaml additive** — optional `destinations:` section under `ingestion:`
- **Runtime capability detection** — `isinstance(plugin, SinkConnector)`

### SinkConnector Interface (from Epic 4F Research, Option C)

```python
# NEW (opt-in mixin):
class SinkConnector(ABC):
    """Optional mixin for plugins that support reverse ETL / data egress."""

    @abstractmethod
    def list_available_sinks(self) -> list[str]:
        """List available sink/destination connectors."""
        ...

    @abstractmethod
    def create_sink(self, config: SinkConfig) -> Any:
        """Create a sink pipeline."""
        ...

    @abstractmethod
    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        """Write data to external destination."""
        ...

    @abstractmethod
    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        """Get lakehouse source config (reverse of get_destination_config)."""
        ...


# dlt implements both:
class DltIngestionPlugin(IngestionPlugin, SinkConnector):
    """dlt supports both ingestion and reverse ETL."""
    ...

# Custom source-only plugin:
class CustomSourcePlugin(IngestionPlugin):
    """No SinkConnector — ingestion only."""
    ...
```

### Data Flow

```
INGESTION (Epic 4F):
  External Source --> dlt --> Iceberg (Bronze) --> dbt (Silver/Gold)

EGRESS (Epic 4G):
  Iceberg (Gold) --> dlt @dlt.destination --> SaaS APIs / Databases
```

---

## File Ownership (Exclusive)

```text
# Core ABC (MODIFY EXISTING)
packages/floe-core/src/floe_core/plugins/
  ingestion.py               # Add SinkConnector ABC mixin + SinkConfig + EgressResult

# dlt Plugin Extension (MODIFY EXISTING from Epic 4F)
plugins/floe-ingestion-dlt/
  src/floe_ingestion_dlt/
    sinks.py                 # SinkConnector implementation via @dlt.destination
    sink_config.py           # Sink-specific Pydantic models

# floe.yaml schema (MODIFY EXISTING)
packages/floe-core/src/floe_core/schemas/
  floe_spec.py               # Add optional destinations: section under ingestion:

# Test fixtures
testing/fixtures/egress.py

# Contract tests
tests/contract/test_sink_connector_abc.py
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 4F | Requires IngestionPlugin + DltIngestionPlugin |
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 4C | Catalog for reading Iceberg tables |
| Blocked By | Epic 4D | Storage for data files |
| Optional | Epic 5A | dbt Gold layer provides curated data for egress |

---

## User Stories (for SpecKit)

### US1: SinkConnector ABC (P0)

**As a** plugin developer
**I want** a clear mixin ABC for reverse ETL capabilities
**So that** plugins can optionally support data egress alongside ingestion

**Acceptance Criteria**:
- [ ] `SinkConnector` ABC defined as mixin in floe-core
- [ ] `list_available_sinks()`, `create_sink()`, `write()`, `get_source_config()` defined
- [ ] `SinkConfig` and `EgressResult` dataclasses defined
- [ ] Runtime capability detection: `isinstance(plugin, SinkConnector)` works

### US2: dlt Reverse ETL Implementation (P0)

**As a** data engineer
**I want** dlt to push Gold layer data to SaaS APIs
**So that** curated data reaches operational systems without custom ETL

**Acceptance Criteria**:
- [ ] `DltIngestionPlugin` also implements `SinkConnector`
- [ ] Uses dlt's `@dlt.destination` decorator for custom sinks
- [ ] Supports writing to REST APIs, databases, and SaaS tools
- [ ] Rate limiting and idempotency handled

### US3: Egress Configuration in floe.yaml (P1)

**As a** data engineer
**I want** to define egress destinations in floe.yaml
**So that** reverse ETL is configured alongside ingestion

**Acceptance Criteria**:
- [ ] Optional `destinations:` section under `ingestion:` in floe.yaml
- [ ] Each destination specifies: name, sink_type, sink_config, source_table
- [ ] Compiler resolves egress config into CompiledArtifacts (additive)

---

## Technical Notes

### Key Decisions

1. **SinkConnector is a mixin, not a plugin type** — zero breaking changes
2. **dlt handles both directions** — same framework, different direction
3. **Progressive disclosure** — teams not needing egress never see SinkConnector
4. **Future extensible** — `StreamConnector`, `CDCConnector`, `BulkExporter` follow same mixin pattern

### Reverse ETL Unique Concerns

| Concern | Mitigation |
|---------|------------|
| SaaS API rate limiting | dlt has built-in rate limiting |
| Field mapping (lakehouse → SaaS schema) | Configuration-driven mapping in sink_config |
| Idempotency | dlt destination decorator supports idempotent writes |
| API evolution (SaaS breaking changes) | Version pinning + schema validation |

### Research Reference

See `.omc/research/epic-4f-ingestion-plugin-research.md` Section 3 for full analysis of:
- Industry trend toward unified data movement
- Three options evaluated (Rename=4.7, Separate=5.6, Mixin=8.2)
- Why Option C (SinkConnector mixin) won

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| dlt `@dlt.destination` maturity | MEDIUM | MEDIUM | Fallback to custom Python sinks |
| SaaS API breaking changes | HIGH | LOW | Version pinning, schema validation |
| Rate limiting complexity | MEDIUM | MEDIUM | dlt built-in + configurable backoff |

### Test Strategy

- **Unit**: `plugins/floe-ingestion-dlt/tests/unit/test_sinks.py`
- **Contract**: `tests/contract/test_sink_connector_abc.py`
- **Integration**: dlt writing to mock SaaS API endpoint

---

## SpecKit Context

### Relevant Codebase Paths
- `packages/floe-core/src/floe_core/plugins/ingestion.py` (add mixin)
- `plugins/floe-ingestion-dlt/` (add sink support)
- `.omc/research/epic-4f-ingestion-plugin-research.md` (research synthesis)

### Related Existing Code
- `IngestionPlugin` ABC from Epic 4F
- `DltIngestionPlugin` from Epic 4F
- `PluginRegistry` from Epic 1

### External Dependencies
- `dlt>=1.20.0` (reverse ETL via `@dlt.destination`)
