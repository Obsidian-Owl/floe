# Implementation Plan: Manifest Schema

**Branch**: `001-manifest-schema` | **Date**: 2026-01-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-manifest-schema/spec.md`

## Summary

Define the unified manifest.yaml schema using Pydantic v2 with support for both 2-tier (single platform) and 3-tier (Data Mesh) configurations. The schema includes plugin selections, governance policies, secret references, and three-tier inheritance with immutable security policies. Environment handling is runtime-based via FLOE_ENV (no compile-time env_overrides).

## Technical Context

**Language/Version**: Python 3.10+ (required for improved importlib.metadata.entry_points API)
**Primary Dependencies**: Pydantic v2 (BaseModel, Field, ConfigDict, field_validator), PyYAML, structlog
**Storage**: N/A (schema definitions only; OCI registry loading deferred to Epic 2B)
**Testing**: pytest, pytest-cov, mypy --strict
**Target Platform**: Python library (floe-core package)
**Project Type**: Monorepo package (packages/floe-core/)
**Performance Goals**: Schema validation < 100ms for typical manifest
**Constraints**: Pydantic v2 syntax only; JSON Schema exportable for IDE autocomplete
**Scale/Scope**: ~15-20 Pydantic models for complete manifest schema

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core for schemas)
- [x] No SQL parsing/validation in Python (N/A - this is config schema)
- [x] No orchestration logic outside floe-dagster (N/A - this is config schema)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC) - manifest references plugins by name
- [x] Plugin registered via entry point (not direct import) - schema validates against plugin registry
- [x] PluginMetadata declares name, version, floe_api_version - referenced in plugin selection schema

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s) - not affected by schema
- [x] Pluggable choices documented in manifest.yaml - this is the purpose of the feature

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling) - manifest is input to compilation
- [x] Pydantic v2 models for all schemas - core requirement
- [x] Contract changes follow versioning rules - apiVersion field included

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster - unit tests for schema validation
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic - core purpose
- [x] Credentials use SecretStr - SecretReference model defined
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only - manifest is Layer 2 (Configuration)
- [x] Layer ownership respected (Data Team vs Platform Team) - manifest owned by Platform Team

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted - N/A for schema validation
- [x] OpenLineage events for data transformations - N/A for schema validation

## Project Structure

### Documentation (this feature)

```text
specs/001-manifest-schema/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (JSON Schema)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
packages/floe-core/
├── src/
│   └── floe_core/
│       ├── __init__.py
│       └── schemas/
│           ├── __init__.py
│           ├── manifest.py         # PlatformManifest, GovernanceConfig
│           ├── plugins.py          # PluginSelection, plugin category schemas
│           ├── secrets.py          # SecretReference
│           ├── metadata.py         # ManifestMetadata
│           ├── inheritance.py      # InheritanceChain, merge utilities
│           └── validation.py       # Cross-field validators, security policy checks
└── tests/
    ├── unit/
    │   └── schemas/
    │       ├── test_manifest.py
    │       ├── test_plugins.py
    │       ├── test_governance.py
    │       ├── test_secrets.py
    │       └── test_inheritance.py
    └── conftest.py

tests/contract/
├── test_manifest_schema.py         # Schema stability tests
├── test_manifest_json_schema.py    # JSON Schema export tests
└── test_manifest_inheritance.py    # Cross-package inheritance tests
```

**Structure Decision**: Single package (floe-core) with schema modules. Contract tests at root level for cross-package validation.

## Complexity Tracking

> No Constitution Check violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
