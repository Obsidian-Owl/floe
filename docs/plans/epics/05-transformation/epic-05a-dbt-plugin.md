# Epic 5A: dbt Plugin

## Summary

The dbt plugin integrates dbt Core with the floe platform. It handles profiles.yml generation, dbt command execution, manifest.json parsing, and Dagster asset generation. dbt is ENFORCED as the transformation framework - all SQL compilation happens through dbt.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-05a-dbt-plugin](https://linear.app/obsidianowl/project/floe-05a-dbt-plugin-fc0710ba388c)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-051 | DBTPlugin implementation | CRITICAL |
| REQ-052 | profiles.yml generation | CRITICAL |
| REQ-053 | dbt command execution | CRITICAL |
| REQ-054 | manifest.json parsing | HIGH |
| REQ-055 | Dagster dbt asset integration | CRITICAL |
| REQ-056 | Multi-target support | HIGH |
| REQ-057 | Incremental model support | HIGH |
| REQ-058 | dbt test execution | HIGH |
| REQ-059 | Source freshness checks | MEDIUM |
| REQ-060 | Documentation generation | MEDIUM |
| REQ-061 | Seed data handling | LOW |
| REQ-062 | Macro support | MEDIUM |
| REQ-063 | Package management | MEDIUM |
| REQ-064 | Run results tracking | HIGH |
| REQ-065 | Compilation caching | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0008](../../../architecture/adr/0008-dbt-integration.md) - dbt integration strategy
- [ADR-0009](../../../architecture/adr/0009-dbt-owns-sql.md) - dbt owns SQL principle

### Interface Docs
- [dbt-integration.md](../../../architecture/transformation/dbt-integration.md) - dbt integration guide

### Contracts
- `DBTPlugin` - dbt integration class
- `ProfileGenerator` - profiles.yml generation
- `ManifestParser` - manifest.json parsing

---

## File Ownership (Exclusive)

```text
packages/floe-dbt/
├── src/floe_dbt/
│   ├── __init__.py
│   ├── plugin.py                # DBTPlugin class
│   ├── profiles.py              # ProfileGenerator
│   ├── manifest.py              # ManifestParser
│   ├── runner.py                # dbt command runner
│   ├── assets.py                # Dagster asset generation
│   └── config.py                # dbt configuration
└── tests/
    ├── unit/
    └── integration/

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/dbt.py              # DBTPlugin test fixtures
testing/fixtures/sample_dbt_project/ # Sample dbt project for testing
testing/tests/unit/test_dbt_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 2B | Uses CompiledArtifacts for profile generation |
| Blocked By | Epic 4A | Uses compute plugin for connections |
| Blocked By | Epic 4B | Generates Dagster assets |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
| Blocks | Epic 5B | Data quality integrates with dbt tests |
| Blocks | Epic 6B | OpenLineage captures dbt lineage |

---

## User Stories (for SpecKit)

### US1: Profile Generation (P0)
**As a** data engineer
**I want** profiles.yml generated automatically
**So that** I don't configure dbt connections manually

**Acceptance Criteria**:
- [ ] Profiles generated from CompiledArtifacts
- [ ] Multiple targets supported (dev, staging, prod)
- [ ] Credential placeholders resolved at runtime
- [ ] Compute plugin config mapped to dbt profile

### US2: Dagster Asset Generation (P0)
**As a** data engineer
**I want** dbt models as Dagster assets
**So that** I get orchestration and lineage automatically

**Acceptance Criteria**:
- [ ] `@dbt_assets` decorator generates assets
- [ ] Model dependencies preserved
- [ ] Asset metadata from dbt manifest
- [ ] Partitioned assets from incremental models

### US3: dbt Command Execution (P1)
**As a** data engineer
**I want** dbt commands executed via floe
**So that** I have consistent execution environment

**Acceptance Criteria**:
- [ ] `floe dbt run` wraps dbt run
- [ ] `floe dbt test` wraps dbt test
- [ ] Output captured and logged
- [ ] Exit codes propagated correctly

### US4: Multi-Target Support (P1)
**As a** data engineer
**I want** different targets for different environments
**So that** I can develop locally and deploy to production

**Acceptance Criteria**:
- [ ] `--target` flag on all commands
- [ ] Target from environment variable
- [ ] Target-specific connection strings
- [ ] Target validation at compile time

### US5: Incremental Model Support (P1)
**As a** data engineer
**I want** incremental models to work with Iceberg
**So that** I can process large datasets efficiently

**Acceptance Criteria**:
- [ ] Incremental strategy mapped to Iceberg merge
- [ ] `is_incremental()` macro works correctly
- [ ] Partition-based incremental support
- [ ] Full refresh option available

---

## Technical Notes

### Key Decisions
- dbt is ENFORCED (not pluggable) - all SQL goes through dbt
- Python dbtRunner API used (not subprocess)
- profiles.yml generated at compile time, credentials resolved at runtime
- dagster-dbt package used for Dagster integration

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| dbt version compatibility | MEDIUM | HIGH | Pin major version, test upgrades |
| Profile generation complexity | MEDIUM | MEDIUM | Comprehensive test coverage |
| Iceberg adapter maturity | MEDIUM | HIGH | Contribute upstream, workarounds |

### Test Strategy
- **Unit**: `packages/floe-dbt/tests/unit/test_profile_generator.py`
- **Integration**: `packages/floe-dbt/tests/integration/test_dbt_run.py`
- **Contract**: `tests/contract/test_core_to_dbt_contract.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/`
- `docs/architecture/transformation/`
- `packages/floe-dbt/`

### Related Existing Code
- CompiledArtifacts from Epic 2B
- ComputePlugin from Epic 4A
- OrchestratorPlugin from Epic 4B

### External Dependencies
- `dbt-core>=1.7.0`
- `dagster-dbt>=0.21.0`
- Compute-specific adapters (dbt-duckdb, dbt-snowflake, etc.)
