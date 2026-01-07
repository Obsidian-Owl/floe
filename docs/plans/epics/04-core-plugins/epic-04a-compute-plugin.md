# Epic 4A: Compute Plugin

## Summary

The ComputePlugin ABC defines the interface for query execution engines. The reference implementation uses DuckDB for local development, with adapters for Snowflake, BigQuery, Databricks, and Spark for production workloads.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-04a-compute-plugin](https://linear.app/obsidianowl/project/floe-04a-compute-plugin-3dce91e48fe9)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-011 | ComputePlugin ABC definition | CRITICAL |
| REQ-012 | Connection pooling interface | HIGH |
| REQ-013 | Query execution abstraction | CRITICAL |
| REQ-014 | DuckDB reference implementation | CRITICAL |
| REQ-015 | Snowflake adapter interface | HIGH |
| REQ-016 | BigQuery adapter interface | MEDIUM |
| REQ-017 | Spark adapter interface | MEDIUM |
| REQ-018 | Connection health monitoring | HIGH |
| REQ-019 | Query timeout handling | HIGH |
| REQ-020 | Resource limit enforcement | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture
- [ADR-0004](../../../architecture/adr/0004-compute-abstraction.md) - Compute abstraction layer

### Interface Docs
- [plugin-interfaces.md](../../../architecture/plugin-system/plugin-interfaces.md) - Plugin interface definitions

### Contracts
- `ComputePlugin` - Query execution ABC
- `ConnectionConfig` - Connection configuration model
- `QueryResult` - Query result wrapper

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_interfaces.py         # ComputePlugin ABC (shared)
└── plugins/
    └── compute/
        └── __init__.py          # Compute plugin package

plugins/floe-compute-duckdb/
├── src/floe_compute_duckdb/
│   ├── __init__.py
│   ├── plugin.py                # DuckDBComputePlugin
│   ├── connection.py            # Connection management
│   └── config.py                # DuckDB config
└── tests/
    ├── unit/
    └── integration/
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocks | Epic 5A | dbt uses compute for execution |
| Blocks | Epic 9A | K8s deployment needs compute config |

---

## User Stories (for SpecKit)

### US1: ComputePlugin ABC (P0)
**As a** plugin developer
**I want** a clear ABC for compute plugins
**So that** I can implement adapters for new engines

**Acceptance Criteria**:
- [ ] `ComputePlugin.execute(query)` defined
- [ ] `ComputePlugin.connect()` and `disconnect()` defined
- [ ] `ComputePlugin.health_check()` defined
- [ ] Configuration via Pydantic models

### US2: DuckDB Reference Implementation (P0)
**As a** data engineer
**I want** DuckDB as the default compute engine
**So that** I can develop locally without cloud dependencies

**Acceptance Criteria**:
- [ ] `DuckDBComputePlugin` implements ABC
- [ ] In-memory and file-based modes
- [ ] Iceberg table support via DuckDB extensions
- [ ] Profile generation for dbt-duckdb

### US3: Connection Health Monitoring (P1)
**As a** platform operator
**I want** connection health monitored
**So that** I can detect issues proactively

**Acceptance Criteria**:
- [ ] Health check endpoint/method
- [ ] Metrics emitted via OpenTelemetry
- [ ] Automatic reconnection on failure
- [ ] Connection pool statistics

### US4: Query Timeout Handling (P1)
**As a** platform operator
**I want** query timeouts enforced
**So that** runaway queries don't consume resources

**Acceptance Criteria**:
- [ ] Configurable timeout per query
- [ ] Default timeout from manifest
- [ ] Graceful cancellation
- [ ] Timeout events logged

---

## Technical Notes

### Key Decisions
- DuckDB is the default (zero-config local development)
- Connection pooling managed per-plugin
- Query results are lazy (streaming support)
- Compute plugins are stateless (no query caching)

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Engine-specific SQL syntax | HIGH | MEDIUM | dbt handles dialect translation |
| Connection leak | MEDIUM | HIGH | Context managers, health checks |
| DuckDB memory limits | MEDIUM | MEDIUM | Configurable memory limits |

### Test Strategy
- **Unit**: `plugins/floe-compute-duckdb/tests/unit/test_plugin.py`
- **Integration**: `plugins/floe-compute-duckdb/tests/integration/test_duckdb_iceberg.py`
- **Contract**: `tests/contract/test_compute_plugin_abc.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/`
- `docs/architecture/plugin-system/`
- `packages/floe-core/src/floe_core/plugin_interfaces.py`
- `plugins/floe-compute-duckdb/`

### Related Existing Code
- PluginRegistry from Epic 1

### External Dependencies
- `duckdb>=0.9.0`
- `duckdb-iceberg` (extension)
