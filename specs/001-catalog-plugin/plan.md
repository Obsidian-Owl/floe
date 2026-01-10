# Implementation Plan: Catalog Plugin

**Branch**: `001-catalog-plugin` | **Date**: 2026-01-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-catalog-plugin/spec.md`

## Summary

Implement the CatalogPlugin ABC in floe-core and PolarisCatalogPlugin reference implementation for Apache Iceberg catalog management. The ABC defines methods for catalog connection (`connect()`), namespace management, table operations, and credential vending. Polaris implementation uses PyIceberg with OAuth2 authentication and emits OpenTelemetry traces for all operations.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: PyIceberg >=0.5.0, Pydantic v2, structlog, opentelemetry-api, httpx (for OAuth2)
**Storage**: N/A (catalog manages metadata; storage is handled by StoragePlugin)
**Testing**: pytest with K8s-native testing (Kind cluster), pytest-asyncio for integration tests
**Target Platform**: Linux containers on Kubernetes
**Project Type**: Plugin package (floe-core ABC + plugins/floe-catalog-polaris implementation)
**Performance Goals**: Catalog operations complete within 2 seconds; health checks within 1 second
**Constraints**: No hardcoded credentials; all secrets via SecretStr/environment; OTel traces required
**Scale/Scope**: Single catalog per deployment; support for 1000+ tables across 100+ namespaces

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core for ABC, plugins/floe-catalog-polaris for implementation)
- [x] No SQL parsing/validation in Python (catalog manages metadata, not SQL)
- [x] No orchestration logic outside floe-dagster (catalog is a service, not orchestration)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (CatalogPlugin ABC)
- [x] Plugin registered via entry point (`floe.catalogs` entry point group)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg table format, OTel observability)
- [x] Pluggable choices documented in manifest.yaml (catalog selection)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (catalog config flows through compilation)
- [x] Pydantic v2 models for all schemas (PolarisCatalogConfig, NamespaceConfig, etc.)
- [x] Contract changes follow versioning rules (CatalogPlugin ABC versioned)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (real Polaris instance)
- [x] No `pytest.skip()` usage (tests fail when infrastructure missing)
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (all config models)
- [x] Credentials use SecretStr (OAuth2 client credentials)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → plugin config)
- [x] Layer ownership respected (Platform Team selects catalog in manifest.yaml)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (FR-030 to FR-032)
- [x] OpenLineage events for data transformations (N/A - catalog is metadata, lineage from orchestrator)

## Project Structure

### Documentation (this feature)

```text
specs/001-catalog-plugin/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
packages/floe-core/
├── src/floe_core/
│   ├── plugins/
│   │   └── catalog.py           # CatalogPlugin ABC (UPDATE existing)
│   ├── plugin_errors.py         # NotSupportedError (if not exists)
│   └── __init__.py              # Export CatalogPlugin
└── tests/
    └── unit/
        └── plugins/
            └── test_catalog_abc.py  # ABC compliance tests

plugins/floe-catalog-polaris/
├── pyproject.toml               # Entry point: floe.catalogs = polaris
├── src/floe_catalog_polaris/
│   ├── __init__.py
│   ├── plugin.py                # PolarisCatalogPlugin implementation
│   ├── config.py                # PolarisCatalogConfig Pydantic model
│   ├── client.py                # Polaris REST client wrapper
│   ├── namespace.py             # Namespace management helpers
│   ├── credentials.py           # Credential vending implementation
│   └── tracing.py               # OTel instrumentation helpers
└── tests/
    ├── conftest.py              # Fixtures (no __init__.py)
    ├── unit/
    │   ├── test_plugin.py
    │   ├── test_config.py
    │   └── test_credentials.py
    └── integration/
        ├── conftest.py          # Polaris fixtures
        ├── test_polaris_connection.py
        ├── test_namespace_operations.py
        └── test_credential_vending.py

tests/contract/
└── test_catalog_plugin_abc.py   # Cross-package ABC compliance

testing/base_classes/
└── base_catalog_plugin_tests.py # BaseCatalogPluginTests for plugin compliance
```

**Structure Decision**: Plugin architecture with ABC in floe-core and reference implementation in plugins/floe-catalog-polaris. This follows the established pattern from Epic 1 (plugin registry) and other plugin types.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
