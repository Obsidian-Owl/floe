# Implementation Plan: K8s RBAC Plugin System

**Branch**: `floe-07b-k8s-rbac` | **Date**: 2026-01-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/7b-k8s-rbac/spec.md`

## Summary

Implement a Kubernetes RBAC Plugin System that provides service account management, namespace isolation with Pod Security Standards, and RBAC manifest generation for the floe platform. The system follows the established plugin ABC pattern from Epic 7A, with `RBACPlugin` extending `PluginMetadata` and `K8sRBACPlugin` as the default implementation using the official kubernetes Python client library.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: kubernetes>=27.0.0, pydantic>=2.0.0, pyyaml>=6.0, structlog
**Storage**: File-based (YAML manifests in `target/rbac/` directory)
**Testing**: pytest with K8s-native testing (Kind cluster), BaseRBACPluginTests compliance suite
**Target Platform**: Kubernetes 1.28+ with Pod Security Admission enabled
**Project Type**: Monorepo package (floe-core extension + plugin)
**Performance Goals**: Generate RBAC manifests in <5s for 100 data products
**Constraints**: No wildcard RBAC permissions, least-privilege only, PSS restricted by default
**Scale/Scope**: Support up to 100 namespaces, 500 service accounts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core for ABC, plugin for implementation)
- [x] No SQL parsing/validation in Python (dbt owns SQL) - N/A for RBAC
- [x] No orchestration logic outside floe-dagster - N/A for RBAC

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC) - RBACPlugin ABC
- [x] Plugin registered via entry point (not direct import) - floe.rbac entry point
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s) - K8s RBAC enforced
- [x] Pluggable choices documented in manifest.yaml - security section

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling) - SecurityConfig in artifacts
- [x] Pydantic v2 models for all schemas - ConfigDict(frozen=True, extra="forbid")
- [x] Contract changes follow versioning rules

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic - All config models use Pydantic
- [x] Credentials use SecretStr - N/A (RBAC doesn't handle secrets directly)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only - manifest.yaml → RBAC manifests
- [x] Layer ownership respected (Data Team vs Platform Team) - Platform Team owns security

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted - RBAC generation operations traced
- [x] OpenLineage events for data transformations - N/A for RBAC

## Project Structure

### Documentation (this feature)

```text
specs/7b-k8s-rbac/
├── spec.md              # Feature specification with user stories and requirements
├── plan.md              # This file
├── research.md          # Technology decisions and integration patterns
├── data-model.md        # Entity definitions with Pydantic models
├── quickstart.md        # Usage guide and troubleshooting
├── contracts/           # Interface and schema contracts
│   ├── rbac-plugin-interface.md
│   └── security-config-schema.md
└── checklists/
    └── requirements.md  # Specification quality validation
```

### Source Code (repository root)

```text
packages/floe-core/
├── src/floe_core/
│   ├── plugins/
│   │   └── rbac.py              # RBACPlugin ABC (NEW)
│   ├── schemas/
│   │   ├── security.py          # SecurityConfig, RBACConfig, PodSecurityLevelConfig (NEW)
│   │   └── rbac.py              # ServiceAccountConfig, RoleConfig, etc. (NEW)
│   └── rbac/
│       └── generator.py         # RBACManifestGenerator (NEW)
└── tests/
    ├── unit/
    │   ├── test_rbac_plugin.py
    │   └── test_rbac_schemas.py
    └── integration/
        └── test_rbac_generator.py

plugins/floe-rbac-k8s/                # K8s RBAC Plugin Implementation (NEW PACKAGE)
├── pyproject.toml
├── src/floe_rbac_k8s/
│   ├── __init__.py
│   └── plugin.py                # K8sRBACPlugin implementation
└── tests/
    ├── unit/
    │   └── test_k8s_rbac_plugin.py
    └── integration/
        └── test_k8s_rbac_integration.py

testing/
└── base_classes/
    └── base_rbac_plugin_tests.py    # BaseRBACPluginTests (NEW)

tests/contract/
└── test_rbac_plugin_contract.py     # Cross-package contract tests (NEW)
```

**Structure Decision**: Monorepo package structure following Epic 7A pattern. RBACPlugin ABC in floe-core, K8sRBACPlugin implementation in plugins/floe-rbac-k8s/, base test class in testing/base_classes/.

## Complexity Tracking

No constitution violations requiring justification. All patterns follow established Epic 7A conventions.

## Implementation Phases

### Phase 1: Core ABC and Schemas

1. Create `RBACPlugin` ABC in `floe_core/plugins/rbac.py`
2. Create Pydantic schemas in `floe_core/schemas/`:
   - `security.py`: SecurityConfig, RBACConfig, PodSecurityLevelConfig
   - `rbac.py`: ServiceAccountConfig, RoleConfig, RoleBindingConfig, NamespaceConfig, PodSecurityConfig
3. Create `BaseRBACPluginTests` in `testing/base_classes/`

### Phase 2: Manifest Generator

1. Create `RBACManifestGenerator` in `floe_core/rbac/generator.py`
2. Implement permission aggregation logic
3. Implement manifest file writing (YAML output)

### Phase 3: K8s Plugin Implementation

1. Create `plugins/floe-rbac-k8s/` package structure
2. Implement `K8sRBACPlugin` class
3. Register via entry point in pyproject.toml

### Phase 4: CLI Integration

1. Add `floe rbac generate` command
2. Add `floe rbac validate` command
3. Add `floe rbac audit` command
4. Add `floe rbac diff` command

### Phase 5: Integration Testing

1. Unit tests for all schemas and ABC
2. Integration tests with Kind cluster
3. Contract tests for cross-package integration
4. E2E tests for full workflow

## Key Design Decisions

See [research.md](./research.md) for detailed rationale:

1. **RBACPlugin ABC Location**: `floe_core/plugins/rbac.py` (follows existing pattern)
2. **Kubernetes Client**: Official `kubernetes` Python client v27+
3. **YAML Generation**: Pydantic models → `yaml.safe_dump(model.model_dump())`
4. **Manifest Output**: Separate files per resource type in `target/rbac/`
5. **Test Pattern**: `BaseRBACPluginTests` with `@pytest.mark.requirement()` markers

## Dependencies

| Dependency | Status | Impact |
|------------|--------|--------|
| Epic 7A (Identity & Secrets) | Complete | SecretsPlugin for secret reference resolution |
| Epic 2B (Compilation Pipeline) | Complete | Integration point for RBAC generation stage |
| Epic 7C (Network/Pod Security) | Future | Network policies (out of scope for 7B) |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| K8s API version incompatibility | Target K8s 1.28+, use stable v1 APIs only |
| Overly permissive RBAC generation | Validation layer prevents wildcard permissions |
| PSS admission blocking pods | Generate compliant securityContext by default |
| Cross-namespace permission leakage | Explicit namespace scoping, audit logging |
