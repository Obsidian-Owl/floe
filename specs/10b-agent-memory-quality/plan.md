# Implementation Plan: Agent Memory Validation & Quality

**Branch**: `10b-agent-memory-quality` | **Date**: 2026-01-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/10b-agent-memory-quality/spec.md`

## Summary

Address testing gaps from Epic 10A by implementing contract tests for Cognee Cloud API field validation, adding load assurance with optional verify flag, and implementing cognify status polling. The goal is to prevent future API contract bugs like the "dad jokes" incident through comprehensive test coverage.

**Research Update**: Memify cannot be refactored to REST API as no `/api/v1/memify` endpoint exists in Cognee Cloud. The cogwit_sdk dependency is retained for memify only; all other operations use REST API.

## Technical Context

**Language/Version**: Python 3.10+ (required for floe-core compatibility)
**Primary Dependencies**: httpx (HTTP client), pytest (testing), structlog (logging), pydantic (validation)
**Storage**: Cognee Cloud (SaaS) - REST API integration, no local storage
**Testing**: pytest with pytest-asyncio, pytest-cov for coverage
**Target Platform**: Linux/macOS development, CI/CD pipelines
**Project Type**: Single package (devtools/agent-memory)
**Performance Goals**: Contract tests < 5s, unit tests < 30s, integration tests < 5 min
**Constraints**: Cognee Cloud API rate limits, async operations require polling
**Scale/Scope**: ~800 LOC CogneeClient, ~21 functional requirements, ~10 success criteria

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (devtools/agent-memory - internal tooling)
- [x] No SQL parsing/validation in Python (N/A - this is API client code)
- [x] No orchestration logic outside floe-dagster (N/A - this is test/validation tooling)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (N/A - not a plugin, internal dev tool)
- [x] Plugin registered via entry point (N/A)
- [x] PluginMetadata declares name, version, floe_api_version (N/A)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (N/A - internal tooling doesn't affect enforced standards)
- [x] Pluggable choices documented in manifest.yaml (N/A)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (N/A - internal tool, no cross-package data)
- [x] Pydantic v2 models for all schemas (existing models in agent_memory.models)
- [x] Contract changes follow versioning rules (N/A - internal API, not cross-package contract)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (integration tests use Cognee Cloud, not K8s services)
- [x] No `pytest.skip()` usage (enforced in all new tests)
- [x] `@pytest.mark.requirement()` on all integration tests (enforced for all tests)

**Principle VI: Security First**
- [x] Input validation via Pydantic (existing config uses Pydantic)
- [x] Credentials use SecretStr (COGNEE_API_KEY already uses SecretStr)
- [x] No shell=True, no dynamic code execution on untrusted data (no shell usage)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (N/A - internal tooling)
- [x] Layer ownership respected (devtools is internal, not part of 4-layer model)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (existing structlog integration)
- [x] OpenLineage events for data transformations (N/A - not a data transformation)

**Constitution Status**: PASS - All applicable principles satisfied. This is internal developer tooling (devtools/agent-memory), not a core platform component, so several plugin/architecture principles are N/A.

### Post-Design Re-evaluation (Phase 1 Complete)

**Design Decisions Reviewed**:
1. **Contract Tests**: Testing payloads without network - no infrastructure impact ✓
2. **Status Polling**: Uses existing REST API - no new dependencies ✓
3. **Verify Flag**: Optional parameter - backwards compatible ✓
4. **Memify SDK Retention**: Research revealed no REST endpoint exists - SDK kept for pragmatic reasons ✓

**No Constitution Violations Introduced**: All design decisions align with internal tooling patterns.

## Project Structure

### Documentation (this feature)

```text
specs/10b-agent-memory-quality/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (Cognee API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
devtools/agent-memory/
├── pyproject.toml                    # KEEP: cogwit_sdk dependency (no REST endpoint for memify)
├── src/agent_memory/
│   ├── cognee_client.py              # UPDATE: Add verify flag, add status polling (memify stays as SDK)
│   ├── cli.py                        # UPDATE: Add --verify flag to sync command
│   ├── config.py                     # Existing (no changes)
│   └── models.py                     # Existing (no changes)
└── tests/
    ├── conftest.py                   # UPDATE: Add contract test fixtures
    ├── contract/                     # NEW: Contract tests directory
    │   └── test_cognee_api_contract.py
    ├── unit/
    │   ├── test_cognee_client.py     # NEW: CogneeClient unit tests
    │   ├── test_cli_memify.py        # UPDATE: Add SDK error handling tests
    │   └── test_cli_reset.py         # Existing
    └── integration/
        ├── test_dataset_isolation.py # UPDATE: Add status polling
        └── test_sync_cycle.py        # NEW: Full sync verification tests
```

**Structure Decision**: Single package structure within devtools/agent-memory. Tests organized by tier (contract, unit, integration) following project conventions.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
