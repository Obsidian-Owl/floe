# Implementation Plan: OCI Client

**Branch**: `floe-08a-oci-client` | **Date**: 2026-01-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/08a-oci-client/spec.md`

## Summary

Implement an OCI-compliant artifact client for pushing, pulling, inspecting, and listing floe CompiledArtifacts to/from OCI registries. The client uses ORAS Python SDK for registry operations, integrates with SecretsPlugin (Epic 7A) for authentication, and includes resilience patterns (retry, circuit breaker), local caching, and OpenTelemetry observability.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: oras-py (ORAS Python SDK), httpx (HTTP client), pydantic v2 (validation), structlog (logging), opentelemetry-api (tracing)
**Storage**: Local file cache at `/var/cache/floe/oci` (configurable)
**Testing**: pytest with K8s-native integration tests (Harbor in Kind cluster)
**Target Platform**: Linux server, K8s pods (EKS, AKS, GKE)
**Project Type**: Single package within floe-core monorepo
**Performance Goals**: Push < 30s for < 1MB artifacts, Pull cache hit < 100ms
**Constraints**: Zero secrets logged, 99.9% success rate (excluding registry unavailability)
**Scale/Scope**: Support Harbor, ECR, ACR, GAR registries; 10 concurrent pulls without corruption

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`packages/floe-core/src/floe_core/oci/`)
- [x] No SQL parsing/validation in Python (N/A - no SQL involved)
- [x] No orchestration logic outside floe-dagster (N/A - OCI is infrastructure)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (N/A - OCI client is core infrastructure, not pluggable)
- [x] N/A - OCI client is NOT a plugin, it's core infrastructure used by all packages

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (OCI is part of K8s-native infrastructure)
- [x] Pluggable choices documented in manifest.yaml (`artifacts.registry` section)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (OCI client pushes/pulls CompiledArtifacts)
- [x] Pydantic v2 models for all schemas (RegistryConfig, ArtifactManifest, CacheEntry)
- [x] Contract changes follow versioning rules (media type includes version: v1)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (Harbor in Kind)
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (all config models validated)
- [x] Credentials use SecretStr (via SecretsPlugin)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → OCI client)
- [x] Layer ownership respected (Platform Team owns registry config)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (FR-031 to FR-034)
- [x] N/A - OpenLineage for data transformations (OCI is infrastructure, not data transform)

## Project Structure

### Documentation (this feature)

```text
specs/08a-oci-client/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (Pydantic schemas)
│   ├── registry_config.py
│   ├── artifact_manifest.py
│   └── cache_entry.py
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── oci/                         # NEW: OCI client module
│   ├── __init__.py              # Public exports
│   ├── client.py                # OCIClient class (push/pull/inspect/list, registry operations)
│   ├── auth.py                  # Authentication helpers (IRSA, MI, WI, basic, token)
│   ├── manifest.py              # ArtifactManifest, layer management
│   ├── cache.py                 # CacheManager, CacheEntry, LRU eviction
│   ├── resilience.py            # RetryPolicy, CircuitBreaker
│   ├── errors.py                # OCI-specific exceptions
│   └── metrics.py               # OpenTelemetry metrics
├── schemas/
│   └── oci.py                   # NEW: OCI configuration schemas for manifest.yaml
└── cli/
    └── artifact.py              # NEW: CLI commands (push/pull/inspect/list/cache)

packages/floe-core/tests/
├── unit/
│   └── oci/                     # Unit tests for OCI client
│       ├── conftest.py
│       ├── test_client.py
│       ├── test_auth.py
│       ├── test_cache.py
│       ├── test_resilience.py
│       └── test_manifest.py
└── integration/
    └── oci/                     # Integration tests with real registry
        ├── conftest.py
        └── test_registry_operations.py

tests/contract/                  # Root-level contract tests
└── test_oci_compiled_artifacts_contract.py  # Verify OCI client handles CompiledArtifacts
```

**Structure Decision**: OCI client is placed in `packages/floe-core/src/floe_core/oci/` as it is core infrastructure used by CLI and other packages. It is NOT a plugin because OCI distribution is a fundamental requirement, not a pluggable choice.

## Complexity Tracking

> No constitution violations - all checks pass.

| Decision | Rationale | Alternative Considered |
|----------|-----------|------------------------|
| OCI client in floe-core (not plugin) | OCI distribution is fundamental infrastructure | Plugin system - rejected because OCI is not pluggable |
| ORAS Python SDK | CNCF standard, OCI v1.1.1 compliant | Custom HTTP client - rejected due to maintenance burden |
| File-based cache | Simple, reliable, K8s PV compatible | Redis cache - rejected due to deployment complexity |

## Implementation Phases

### Phase 0: Research (Complete)
- [x] Research ORAS Python SDK capabilities
- [x] Research OCI artifact media types
- [x] Research existing floe patterns (Pydantic, plugins)
- [x] Document findings in research.md

### Phase 1: Design & Contracts (Complete)
- [x] Define data models (RegistryConfig, ArtifactManifest, CacheEntry)
- [x] Generate Pydantic schemas in contracts/
- [x] Define CLI interface
- [x] Create quickstart.md

### Phase 2: Tasks (Complete)
- [x] Run `/speckit.tasks` to generate task breakdown (70 tasks across 10 phases)

### Phase 3-10: Implementation (Complete)
- [x] Phase 3: US1 Push (T013-T021) - Push artifacts to OCI registry
- [x] Phase 4: US2 Pull (T022-T030) - Pull artifacts with cache integration
- [x] Phase 5: US3 Inspect (T031-T035) - Inspect artifact metadata
- [x] Phase 6: US4 List (T036-T040) - List tags with filtering
- [x] Phase 7: US5 Resilience (T041-T045) - Retry and circuit breaker
- [x] Phase 8: US6 Caching (T046-T052) - LRU cache with TTL
- [x] Phase 9: US7 Authentication (T053-T060) - Multi-provider auth
- [x] Phase 10: Polish (T061-T068) - Documentation, security, coverage

**Implementation Status**: ✅ Complete (68/70 tasks done, 2 require K8s infrastructure)
**Unit Test Coverage**: 80.17% (156 tests)
**Security Scan**: Passed (bandit, manual review)

## Dependencies

| Dependency | Epic | Status | Impact |
|------------|------|--------|--------|
| CompiledArtifacts | 2B | Complete | OCI client packages this artifact |
| SecretsPlugin | 7A | Complete | Authentication credential resolution |
| Epic 8B (Signing) | 8B | Planned | Hooks prepared, integration deferred |
| Epic 8C (Promotion) | 8C | Planned | Hooks prepared, integration deferred |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| ORAS SDK breaking changes | Pin specific version, comprehensive tests |
| Registry authentication complexity | Start with basic auth, add cloud providers incrementally |
| Cache corruption under concurrency | File locking, atomic writes, digest verification |
| Circuit breaker false positives | Configurable thresholds, half-open probing |
