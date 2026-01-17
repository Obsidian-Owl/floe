# Research: Compilation Pipeline

**Branch**: `2b-compilation-pipeline` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)

## Executive Summary

Research confirms Epic 2B can proceed. Existing infrastructure provides solid foundation:
- CompiledArtifacts schema exists with metadata, identity, and observability fields
- PlatformManifest schema is complete with validation and inheritance
- ComputePlugin ABC with `generate_dbt_profile()` method implemented
- No CLI directory exists - must be created from scratch
- No FloeSpec schema - must be created for `floe.yaml` parsing

## Codebase Analysis

### Existing Components

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| CompiledArtifacts | `schemas/compiled_artifacts.py` | Partial | Has metadata, identity, observability; missing plugins, transforms, dbt_profiles |
| PlatformManifest | `schemas/manifest.py` | Complete | Full validation, scope constraints, environment-agnostic enforcement |
| ComputePlugin | `plugins/compute.py` | Complete | ABC with `generate_dbt_profile()` method |
| DuckDBComputePlugin | `floe-compute-duckdb/plugin.py` | Complete | Reference implementation for profile generation |
| compiler.py | `compiler.py` | Partial | Only handles transform compute resolution, not full compilation |
| CLI | `cli/` | Missing | Directory does not exist |
| FloeSpec | `schemas/` | Missing | No floe.yaml schema defined |

### CompiledArtifacts Schema Analysis

Current fields in `compiled_artifacts.py`:
```python
class CompiledArtifacts(BaseModel):
    version: str = "0.1.0"          # Schema version
    metadata: CompilationMetadata    # compiled_at, floe_version, source_hash, product info
    identity: ProductIdentity        # product_id, domain, repository, namespace_registered
    mode: DeploymentMode            # "simple" | "centralized" | "mesh"
    inheritance_chain: list[ManifestRef]  # Manifest lineage
    observability: ObservabilityConfig    # TelemetryConfig, lineage settings
```

**Fields to Add (per spec FR-003, FR-005, FR-007)**:
- `plugins`: Resolved plugin configuration
- `transforms`: Transform configuration with resolved compute
- `dbt_profiles`: Generated dbt profiles.yml content (as dict)
- `governance`: Resolved governance config

### PlatformManifest Validation

Key validation already implemented:
- Scope constraints (enterprise, domain, None)
- Parent manifest requirements
- Environment-specific field rejection (`FORBIDDEN_ENVIRONMENT_FIELDS`)
- Forward compatibility (unknown field warnings)

### ComputePlugin Interface

The `generate_dbt_profile()` method signature from DuckDB implementation:
```python
def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
    """Generate dbt profile.yml configuration for compute target."""
```

Returns dict structure matching dbt profiles.yml schema.

## Architecture Alignment

### Technology Ownership (Constitution Section I)

| Owner | Responsibility | Epic 2B Interaction |
|-------|---------------|---------------------|
| dbt | SQL compilation, dialect translation | CompiledArtifacts provides profiles.yml config |
| Dagster | Orchestration, assets, schedules | CompiledArtifacts provides configuration DATA |
| floe-core | Compilation, validation | Owns `floe compile` command |

**Key Decision**: floe-core produces CompiledArtifacts containing DATA. floe-dagster consumes this data to generate Dagster Definitions. No code generation in floe-core.

### Environment-Agnostic Compilation (ADR-0039, REQ-151)

Confirmed requirements:
- CompiledArtifacts must contain credential placeholders (`{{ env_var('X') }}`)
- Same artifact digest promotable across dev/staging/prod
- Runtime behavior determined by `FLOE_ENV` environment variable
- No secrets at compile time

### Entry Point Pattern

No existing CLI in floe-core. Standard pattern from pyproject.toml:
```toml
[project.scripts]
floe = "floe_core.cli:main"
```

Will use argparse (stdlib) matching project conventions.

## Open Questions (Resolved)

| # | Question | Resolution |
|---|----------|------------|
| 1 | CLI framework? | argparse (stdlib) - no additional dependencies |
| 2 | Output directory? | `target/` (dbt convention, per existing artifact patterns) |
| 3 | FloeSpec vs DataProduct naming? | Use `FloeSpec` (matches `floe.yaml` → `FloeSpec` pattern) |
| 4 | dbt profiles format? | Dict in CompiledArtifacts, YAML file written separately |
| 5 | Compilation stages? | Fixed 6-stage enum (not generic pipeline) |

## Dependencies

### Blocked By (Verified Available)

- [x] Epic 1 (Plugin Registry): `PluginRegistry` class exists
- [x] Epic 2A (Manifest Schema): `PlatformManifest` complete

### Blocks (Future Epics)

- Epic 3A (Policy Enforcer): Consumes CompiledArtifacts
- Epic 8A (OCI Client): OCI output format deferred

## Risks Identified

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FloeSpec schema changes after Epic 3A | Medium | Medium | Define minimal schema, add fields incrementally |
| dbt profiles.yml format changes | Low | Low | Use ComputePlugin abstraction, isolate format logic |
| CLI argument conflicts with future commands | Low | Low | Reserve common flags (`--verbose`, `--quiet`) |

## Recommendations

1. **Start with FloeSpec schema** - Core dependency for compilation pipeline
2. **Extend CompiledArtifacts incrementally** - Add plugins, transforms, dbt_profiles, governance
3. **Implement CLI with argparse** - No new dependencies, matches project conventions
4. **Use fixed 6-stage enum** - Over-engineering pipeline abstraction adds complexity without value
5. **Write contract tests first** - Schema stability is critical for cross-package integration

## References

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` - Current schema
- `packages/floe-core/src/floe_core/schemas/manifest.py` - PlatformManifest reference
- `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` - Profile generation example
- `docs/architecture/platform-enforcement.md` - Technology ownership
- `docs/architecture/adr/ADR-0039-environment-agnostic.md` - Environment-agnostic design
