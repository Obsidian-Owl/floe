# Epic 4A: Compute Plugin

## Summary

The ComputePlugin ABC defines the interface for query execution engines with **multi-compute pipeline support**:

- **Platform teams** approve N compute targets (DuckDB, Spark, Snowflake, etc.)
- **Data engineers** select compute per-transform from the approved list
- **Hierarchical governance** (Enterprise → Domain → Product) restricts available computes
- **Environment parity** preserved - each transform uses the SAME compute across dev/staging/prod

The reference implementation uses DuckDB for cost-effective analytics, with adapters for Snowflake, BigQuery, Databricks, and Spark.

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
| REQ-012 | Profile generation interface | HIGH |
| REQ-013 | Catalog attachment SQL | HIGH |
| REQ-014 | Connection validation | CRITICAL |
| REQ-015 | Resource requirements | HIGH |
| REQ-016 | Credential delegation | HIGH |
| REQ-017 | Package dependencies | MEDIUM |
| REQ-018 | Error handling | HIGH |
| REQ-019 | Type safety | HIGH |
| REQ-020 | Compliance test suite | MEDIUM |
| REQ-021 | **ComputeRegistry multi-compute support** | CRITICAL |
| REQ-022 | **Per-transform compute selection** | CRITICAL |
| REQ-023 | **Hierarchical compute governance** | HIGH |
| REQ-024 | **Environment parity enforcement** | CRITICAL |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture
- [ADR-0010](../../../architecture/adr/0010-target-agnostic-compute.md) - **Multi-Compute Pipeline Architecture** (KEY ADR)
- [ADR-0038](../../../architecture/adr/0038-data-mesh-architecture.md) - Data Mesh hierarchical governance

### Interface Docs
- [plugin-interfaces.md](../../../architecture/plugin-system/plugin-interfaces.md) - Plugin interface definitions

### Contracts
- `ComputePlugin` - Query execution ABC
- `ComputeRegistry` - Multi-compute configuration holder
- `ComputeConfig` - Single compute target configuration
- `ConnectionConfig` - Connection configuration model

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

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/compute.py          # ComputePlugin test fixtures
testing/tests/unit/test_compute_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
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

### US5: Multi-Compute Pipeline Support (P0)
**As a** data engineer
**I want** to select different compute engines for different pipeline steps
**So that** I can use the right tool for each job (Spark for heavy processing, DuckDB for analytics)

**Acceptance Criteria**:
- [ ] `transforms[].compute` field in floe.yaml
- [ ] Compute must be in platform's approved list
- [ ] Default compute used when not specified
- [ ] Compile-time validation of compute selection

### US6: ComputeRegistry Multi-Compute Configuration (P0)
**As a** platform engineer
**I want** to define N approved compute targets with a default
**So that** data engineers can choose from a governed set

**Acceptance Criteria**:
- [ ] `compute.approved[]` in manifest.yaml
- [ ] `compute.default` specifies fallback
- [ ] All approved computes are loaded and validated
- [ ] Clear error when compute not in approved list

### US7: Hierarchical Compute Governance (P1)
**As an** enterprise architect
**I want** domain teams to restrict available computes to a subset
**So that** different business units can enforce different standards

**Acceptance Criteria**:
- [ ] Enterprise manifest defines global set
- [ ] Domain manifest restricts to subset
- [ ] Validation ensures subset constraint
- [ ] Clear error messages on violation

---

## Technical Notes

### Key Decisions
- DuckDB is the default (zero-config local development)
- **Multi-compute pipelines**: Platform approves N computes, data engineers select per-transform
- **Environment parity**: Each transform uses SAME compute across dev/staging/prod (no drift)
- **Hierarchical governance**: Enterprise → Domain → Product restriction
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
