# Implementation Plan: Compilation Pipeline

**Branch**: `2b-compilation-pipeline` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/2b-compilation-pipeline/spec.md`

## Summary

Implement the `floe compile` command that transforms FloeSpec (floe.yaml) + PlatformManifest into CompiledArtifacts - the sole contract between floe-core and downstream packages. This includes CLI implementation, FloeSpec schema definition, dbt profiles.yml generation, and JSON/YAML serialization.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: Pydantic v2, PyYAML, structlog, argparse (stdlib)
**Storage**: File-based (JSON/YAML artifacts in `target/` directory)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Linux server, macOS (dev), Kubernetes (deployment)
**Project Type**: Monorepo package (floe-core owns compilation)
**Performance Goals**: <5s compilation for 10-50 models (SC-001), <2s dry-run (SC-006)
**Constraints**: Environment-agnostic compilation (FR-014), no secrets at compile-time
**Scale/Scope**: Single data product compilation per invocation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Post-Phase 1 Review** (2026-01-14): All checkboxes verified. Design artifacts (data-model.md, contracts/) confirm compliance. CompiledArtifacts extension uses MINOR version bump (0.1.0 → 0.2.0) per contract versioning rules.

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core owns compilation)
- [x] No SQL parsing/validation in Python (dbt owns SQL via profiles.yml)
- [x] No orchestration logic outside floe-dagster (CompiledArtifacts provides DATA, not code)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ComputePlugin ABC for profile generation)
- [x] Plugin registered via entry point (existing plugin discovery via PluginRegistry)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml (compute, orchestrator, catalog)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling)
- [x] Pydantic v2 models for all schemas (frozen=True, extra="forbid")
- [x] Contract changes follow versioning rules (MAJOR/MINOR/PATCH)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (FloeSpec, PlatformManifest)
- [x] Credentials use SecretStr (never in CompiledArtifacts)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → floe.yaml → CompiledArtifacts)
- [x] Layer ownership respected (Platform Team owns manifest, Data Team owns floe.yaml)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (compilation stages)
- [x] Structured logging via structlog with trace context

## Project Structure

### Documentation (this feature)

```text
specs/2b-compilation-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── compiled-artifacts.json   # JSON Schema
│   └── floe-spec.json            # JSON Schema
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── cli/
│   ├── __init__.py              # CLI entry point
│   └── compile.py               # floe compile command (NEW)
├── compiler.py                  # Existing: transform compute resolution
├── compilation/                 # NEW: compilation pipeline modules
│   ├── __init__.py
│   ├── stages.py                # CompilationStage enum and handlers
│   ├── loader.py                # YAML loading for manifest/floe.yaml
│   ├── resolver.py              # Plugin resolution and inheritance
│   └── builder.py               # CompiledArtifacts builder
├── schemas/
│   ├── compiled_artifacts.py    # Existing: extend with missing fields
│   ├── floe_spec.py             # NEW: FloeSpec (floe.yaml) schema
│   ├── manifest.py              # Existing: PlatformManifest
│   └── ...
└── plugins/
    └── compute.py               # Existing: ComputePlugin ABC

tests/
├── contract/
│   ├── test_compiled_artifacts_schema.py    # Schema stability tests
│   └── test_core_to_dagster_contract.py     # Cross-package contract
└── unit/
    └── floe_core/
        ├── test_compile_command.py          # CLI tests
        ├── test_floe_spec_schema.py         # FloeSpec validation
        └── test_compilation_stages.py       # Stage handler tests
```

**Structure Decision**: Single monorepo package structure. floe-core owns all compilation logic. CLI is a submodule within floe-core (not a separate package) per epic file ownership.

## Implementation Phases

### Phase 1: Core Schemas (P1)

**Goal**: Define FloeSpec schema and extend CompiledArtifacts with missing fields.

1. **FloeSpec Schema** (`schemas/floe_spec.py`)
   - Parse `floe.yaml` data product configuration
   - Fields: apiVersion, kind, metadata, platform, transforms, schedule
   - Validators: environment-agnostic (no env-specific fields)

2. **CompiledArtifacts Extension** (`schemas/compiled_artifacts.py`)
   - Add missing fields: `plugins`, `transforms`, `dbt_profiles`, `governance`
   - Implement `to_json_file()` and `from_json_file()` methods
   - Add `to_yaml_file()` for YAML output

### Phase 2: Compilation Pipeline (P1)

**Goal**: Implement multi-stage compilation pipeline.

1. **Compilation Stages** (`compilation/stages.py`)
   - Define `CompilationStage` enum: LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE
   - Implement stage handlers with structured logging

2. **Loader** (`compilation/loader.py`)
   - Load and validate `floe.yaml` → FloeSpec
   - Load and validate `manifest.yaml` → PlatformManifest

3. **Resolver** (`compilation/resolver.py`)
   - Resolve plugin configurations from manifest
   - Resolve manifest inheritance (3-tier mode)
   - Generate dbt profiles.yml via ComputePlugin.generate_dbt_profile()

4. **Builder** (`compilation/builder.py`)
   - Build CompiledArtifacts from resolved configuration
   - Include metadata (git commit, timestamp, versions)

### Phase 3: CLI Command (P1)

**Goal**: Implement `floe compile` command.

1. **CLI Entry Point** (`cli/compile.py`)
   - argparse-based CLI matching existing patterns
   - Arguments: --spec, --manifest, --output, --dry-run, --validate-only, --format
   - Exit codes: 0=success, 1=validation error, 2=compilation error

2. **Entry Point Registration** (`pyproject.toml`)
   - Add console_scripts entry point for `floe` command

### Phase 4: Integration and Testing (P2)

**Goal**: Contract tests and integration tests.

1. **Contract Tests** (`tests/contract/`)
   - Schema stability tests (round-trip serialization)
   - Cross-package contract tests (floe-dagster consumption)

2. **Unit Tests** (`tests/unit/floe_core/`)
   - CLI argument parsing
   - FloeSpec validation
   - Stage handler execution

## Key Design Decisions

### D1: FloeSpec vs DataProduct Naming

**Decision**: Use `FloeSpec` as the schema name for `floe.yaml`.
**Rationale**: Matches the file naming convention (`floe.yaml` → `FloeSpec`). `DataProduct` is a higher-level concept used in Data Mesh mode.

### D2: dbt Profiles in CompiledArtifacts

**Decision**: Include resolved dbt profiles configuration in CompiledArtifacts as a dict (not raw YAML string).
**Rationale**: Enables downstream tools to inspect/modify profiles. YAML serialization happens at file write time.

### D3: Compilation Stage Enum

**Decision**: Use enum for compilation stages, not a generic pipeline abstraction.
**Rationale**: Fixed 6 stages are spec-mandated. Over-engineering a generic pipeline adds complexity without value.

### D4: Environment-Agnostic Credentials

**Decision**: CompiledArtifacts contains credential placeholders (`{{ env_var('X') }}`), never resolved values.
**Rationale**: Enables "compile once, deploy everywhere" (FR-014). Runtime resolution via FLOE_ENV.

## Complexity Tracking

> No constitution violations. All complexity is justified by spec requirements.

## Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| Epic 1 (Plugin Registry) | Blocked By | Complete (PluginRegistry exists) |
| Epic 2A (Manifest Schema) | Blocked By | Complete (PlatformManifest exists) |
| Epic 3A (Policy Enforcer) | Blocks | Not started (consumes CompiledArtifacts) |
| Epic 8A (OCI Client) | Blocks | Not started (OCI output deferred) |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| FloeSpec schema changes after Epic 3A | Medium | Define minimal schema, add fields incrementally |
| dbt profiles.yml format changes | Low | Use ComputePlugin abstraction, isolate format logic |
| Performance for large projects (>100 models) | Medium | Profile early, defer caching to future epic |
