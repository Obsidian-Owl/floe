# Implementation Plan: Plugin Registry Foundation

**Branch**: `001-plugin-registry` | **Date**: 2026-01-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-plugin-registry/spec.md`

## Summary

Implement the foundational plugin registry system for floe-core that enables plugin discovery, registration, version compatibility checking, and configuration validation. The registry uses Python entry points with type-specific namespaces (11 plugin types) and a common PluginMetadata base ABC that all plugin type interfaces inherit from.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: Pydantic v2 (config validation), structlog (logging)
**Storage**: N/A (in-memory registry, plugins are entry points in installed packages)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Linux server (K8s), macOS (development)
**Project Type**: Single package (`floe-core`)
**Performance Goals**: Discovery <5s startup, lookup <10ms (SC-001, SC-002)
**Constraints**: Graceful degradation on plugin errors, lazy loading
**Scale/Scope**: 11 plugin types, ~10-50 plugins in typical deployment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Based on project principles from CLAUDE.md and TESTING.md:

| Principle | Status | Notes |
|-----------|--------|-------|
| **Technology Ownership** | PASS | Plugin registry owns discovery/registration; delegates SQL to dbt, orchestration to Dagster |
| **Contract-Driven Integration** | PASS | PluginMetadata base ABC defines contract; plugins implement type-specific interfaces |
| **K8s-Native Testing** | PASS | Integration tests run in Kind cluster |
| **Tests FAIL Never Skip** | WILL ENFORCE | All tests must fail on missing infrastructure |
| **Type Safety** | WILL ENFORCE | mypy --strict, Pydantic v2 models |
| **Security First** | PASS | No secrets in registry; config uses SecretStr for credentials |
| **No Hardcoded Sleep** | WILL ENFORCE | Use polling utilities from testing framework |

**Gate Status**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-plugin-registry/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/
├── src/floe_core/
│   ├── __init__.py
│   ├── plugin_registry.py      # PluginRegistry singleton
│   ├── plugin_metadata.py      # PluginMetadata base ABC
│   ├── plugin_types.py         # PluginType enum (11 types)
│   ├── plugin_errors.py        # Custom exceptions
│   ├── version_compat.py       # Semver compatibility logic
│   └── plugins/
│       ├── __init__.py
│       ├── compute.py          # ComputePlugin ABC
│       ├── orchestrator.py     # OrchestratorPlugin ABC
│       ├── catalog.py          # CatalogPlugin ABC
│       ├── storage.py          # StoragePlugin ABC
│       ├── telemetry.py        # TelemetryBackendPlugin ABC
│       ├── lineage.py          # LineageBackendPlugin ABC
│       ├── dbt.py              # DBTPlugin ABC
│       ├── semantic.py         # SemanticLayerPlugin ABC
│       ├── ingestion.py        # IngestionPlugin ABC
│       ├── secrets.py          # SecretsPlugin ABC
│       └── identity.py         # IdentityPlugin ABC
├── tests/
│   ├── conftest.py             # Package fixtures
│   ├── unit/
│   │   ├── conftest.py
│   │   ├── test_plugin_registry.py
│   │   ├── test_plugin_metadata.py
│   │   ├── test_version_compat.py
│   │   └── test_plugin_types.py
│   └── contract/
│       └── test_plugin_abc_contract.py
└── pyproject.toml

tests/                          # Root-level cross-package tests
└── contract/
    └── test_plugin_abc_contract.py  # Verify ABCs stable across versions
```

**Structure Decision**: Single package (`floe-core`) containing all plugin interfaces and registry. Plugin implementations go in separate packages under `plugins/` directory (out of scope for this epic).

## Complexity Tracking

> No violations to justify - design follows established patterns from architecture docs.
