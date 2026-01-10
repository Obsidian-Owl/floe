# Implementation Plan: Compute Plugin ABC with Multi-Compute Pipeline Support

**Branch**: `001-compute-plugin` | **Date**: 2026-01-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-compute-plugin/spec.md`

## Summary

Implement the ComputePlugin abstract base class (ABC) that defines the contract for compute target configuration in the floe platform. The plugin generates dbt profiles.yml configuration (dbt handles SQL execution via its adapters), validates connections via native database drivers for fast health checks, and provides K8s resource requirements for dbt job pods. A DuckDB reference implementation will serve as the default compute for local development with zero external dependencies.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: Pydantic v2 (config validation), structlog (logging), duckdb>=0.9.0 (reference implementation)
**Storage**: N/A (plugin system is stateless; dbt profiles.yml is file-based output)
**Testing**: pytest with K8s-native testing via Kind cluster, IntegrationTestBase
**Target Platform**: Linux server (K8s), macOS/Linux dev (local DuckDB)
**Project Type**: Monorepo plugin package (`plugins/floe-compute-duckdb/`)
**Performance Goals**: Plugin load <5s (SC-003), validate_connection <5s (SC-007 health check)
**Constraints**: No SQL parsing (dbt owns SQL), SecretStr for credentials, OTLP for metrics

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (ComputePlugin ABC in floe-core, DuckDBComputePlugin in plugins/floe-compute-duckdb/)
- [x] No SQL parsing/validation in Python (dbt owns SQL) - spec clarification confirms hybrid approach
- [x] No orchestration logic outside floe-dagster - ComputePlugin only generates config

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC) - ComputePlugin ABC inherits from PluginMetadata
- [x] Plugin registered via entry point (`floe.computes` group)
- [x] PluginMetadata declares name, version, floe_api_version - inherited from existing base class

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg via get_catalog_attachment_sql, OTel metrics, dbt profiles)
- [x] Pluggable choices documented in manifest.yaml (compute.approved, compute.default)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (ComputeConfig is part of artifact)
- [x] Pydantic v2 models for all schemas (ComputeConfig, ConnectionResult, ResourceSpec)
- [x] Contract changes follow versioning rules (new models are additive)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage - tests FAIL if infrastructure missing
- [x] `@pytest.mark.requirement()` on all integration tests - FR-001 through FR-024 coverage

**Principle VI: Security First**
- [x] Input validation via Pydantic (ComputeConfig)
- [x] Credentials use SecretStr (in ConnectionConfig passed to generate_dbt_profile)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml -> ComputeConfig -> profiles.yml)
- [x] Layer ownership respected (Platform Team selects approved computes; Data Team uses them)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (FR-024 metrics requirement)
- [x] OpenLineage events for data transformations (handled by dbt/orchestrator, not ComputePlugin)

## Project Structure

### Documentation (this feature)

```text
specs/001-compute-plugin/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── plugin_metadata.py        # EXISTING - PluginMetadata ABC base class
├── plugin_registry.py        # EXISTING - Plugin discovery and loading
├── plugin_types.py           # EXISTING - PluginType.COMPUTE enum
├── plugin_errors.py          # EXISTING - Exception hierarchy
├── compute_plugin.py         # NEW - ComputePlugin ABC
├── compute_config.py         # NEW - ComputeConfig, ConnectionResult, ResourceSpec models
└── compute_errors.py         # NEW - ComputeConnectionError, ComputeTimeoutError

plugins/floe-compute-duckdb/
├── pyproject.toml            # Entry point: floe.computes = duckdb
├── src/floe_compute_duckdb/
│   ├── __init__.py
│   ├── plugin.py             # DuckDBComputePlugin implementation
│   └── config.py             # DuckDBConfig Pydantic model
└── tests/
    ├── unit/
    │   └── test_plugin.py    # Unit tests (mocked)
    └── integration/
        └── test_duckdb.py    # Integration tests (real DuckDB)

tests/contract/
└── test_compute_plugin_contract.py  # ABC compliance test suite
```

**Structure Decision**: Monorepo plugin package pattern. ComputePlugin ABC lives in floe-core for import by all compute plugins. DuckDBComputePlugin is a separate package in `plugins/` following the established pattern for pluggable components.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | - | - |
