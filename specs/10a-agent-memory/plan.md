# Implementation Plan: Agent Memory (Cognee Integration)

**Branch**: `10a-agent-memory` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/10a-agent-memory/spec.md`

## Summary

Implement persistent, graph-augmented memory for AI coding agents contributing to the floe codebase using Cognee Cloud. The system indexes architecture documentation (45+ ADRs, 22,700+ lines), Python docstrings, and governance rules into a shared knowledge graph. AI agents (Claude Code, Cursor) access memory via MCP protocol for cross-session context preservation, decision traceability, and capability indexing.

**Technical Approach**: Thin wrappers around Cognee Cloud SDK with custom operational tooling (coverage analysis, drift detection, batch loading) that Cognee doesn't provide out-of-box.

## Technical Context

**Language/Version**: Python 3.10+ (Cognee requirement, matches floe standard)
**Primary Dependencies**:
- `cognee>=0.5.0` - Core Cognee SDK
- `cognee-mcp>=0.5.0` - MCP server for Claude Code integration
- `httpx>=0.27.0` - Async HTTP client for API calls
- `structlog` - Structured logging (floe standard)
- `pydantic>=2.0` - Configuration validation (floe standard)

**Storage**: Cognee Cloud (SaaS) - managed vector + graph storage, no self-hosted backends
**Testing**: pytest with async support (`pytest-asyncio`), K8s-native for integration tests
**Target Platform**: Developer workstations (macOS/Linux), CI/CD (GitHub Actions)
**Project Type**: Single Python package (`devtools/agent-memory/`) - internal tooling, not distributed

**Performance Goals**:
- Search response < 3s for typical queries
- Git hook overhead < 500ms (async, non-blocking)
- Batch initial load: progress visible, resumable

**Constraints**:
- Cognee Cloud: 1 GB ingestion + 10,000 API calls ($25/month)
- OpenAI API dependency for LLM-powered cognify
- Async-only SDK (all operations use async/await)

**Scale/Scope**:
- 45+ ADRs, 22,700+ lines architecture docs
- ~50 Python modules with docstrings
- 13 skills, constitution, rules
- Team of ~5-10 contributors

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`devtools/agent-memory/` - internal tooling)
- [x] No SQL parsing/validation in Python (N/A - no SQL in this feature)
- [x] No orchestration logic outside floe-dagster (N/A - no Dagster integration)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (N/A - not a plugin, internal tooling)
- [x] Plugin registered via entry point (N/A - CLI-based tooling)
- [x] PluginMetadata declares name, version, floe_api_version (N/A)

**Note**: This is **devtools** (internal tooling), not a plugin. The plugin architecture principles don't apply. The package will use `"Private :: Do Not Upload"` PyPI classifier.

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s) - N/A, internal tooling
- [x] Pluggable choices documented in manifest.yaml - N/A

**Note**: Agent Memory is orthogonal to the enforced/pluggable architecture; it's developer experience tooling.

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (N/A - no cross-package data flow)
- [x] Pydantic v2 models for all schemas (YES - config and state models use Pydantic)
- [x] Contract changes follow versioning rules (N/A - internal tooling)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (YES - tests requiring Cognee Cloud run in K8s)
- [x] No `pytest.skip()` usage (YES - tests fail if infrastructure missing)
- [x] `@pytest.mark.requirement()` on all integration tests (YES - will implement)

**Principle VI: Security First**
- [x] Input validation via Pydantic (YES - all config uses Pydantic models)
- [x] Credentials use SecretStr (YES - API keys via environment variables, SecretStr in models)
- [x] No shell=True, no dynamic code execution on untrusted data (YES - compliant)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (N/A - internal tooling, not in layer model)
- [x] Layer ownership respected (N/A)

**Note**: Agent Memory sits outside the four-layer model; it's contributor tooling, not platform infrastructure.

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (PARTIAL - structlog for ops logging; OTel optional for graph query tracing)
- [x] OpenLineage events for data transformations (N/A - no data transformations)

**Note**: OTel integration is optional for Epic 10A (listed as "Related" to Epic 6A). Structured logging with structlog is mandatory.

## Project Structure

### Documentation (this feature)

```text
specs/10a-agent-memory/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Cognee research findings
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer onboarding
├── contracts/           # API contracts (internal)
│   ├── cognee-sync.yaml # Sync orchestration interface
│   └── config.yaml      # Configuration schema
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Task breakdown (generated by /speckit.tasks)
```

### Source Code (repository root)

```text
devtools/                              # INTERNAL ONLY - never distributed
└── agent-memory/                      # Cognee integration for AI coding agents
    ├── pyproject.toml                 # "Private :: Do Not Upload" classifier
    ├── README.md                      # Explicit audience statement
    ├── src/agent_memory/
    │   ├── __init__.py                # Package init, version
    │   ├── cli.py                     # Typer CLI for Makefile targets
    │   ├── config.py                  # Pydantic settings model
    │   ├── cognee_client.py           # Thin wrapper around cognee SDK
    │   ├── cognee_sync.py             # Sync orchestration
    │   ├── docstring_extractor.py     # Python docstring → content
    │   ├── markdown_parser.py         # Markdown → content
    │   ├── mcp_config.py              # MCP server configuration helper
    │   └── ops/                       # Operational tooling
    │       ├── __init__.py
    │       ├── health.py              # Health check wrapper
    │       ├── coverage.py            # Indexed vs filesystem analysis
    │       ├── drift.py               # Stale entry detection
    │       ├── batch.py               # Batch load with checkpoints
    │       └── quality.py             # Search quality validation
    └── tests/
        ├── conftest.py                # Shared fixtures
        ├── unit/
        │   ├── test_config.py
        │   ├── test_docstring_extractor.py
        │   ├── test_markdown_parser.py
        │   └── test_ops_coverage.py
        ├── integration/
        │   ├── test_cognee_cloud.py   # Real Cognee Cloud API
        │   └── test_sync_cycle.py     # Full cognify → search
        └── quality/
            └── test_search_quality.py # Known queries → expected results

scripts/
├── setup-hooks.sh                     # Extended with Cognee hooks
└── cognee-sync                        # Sync CLI wrapper

.cognee/
├── config.yaml                        # Cognee Cloud configuration
├── checksums.json                     # Content hashes for drift detection
└── .gitignore                         # Exclude credentials

.github/workflows/
└── cognee-sync.yml                    # CI sync workflow (optional)

Makefile                               # Extended with cognee-* targets
```

**Structure Decision**: Single Python package in `devtools/` following the Epic 10A file ownership specification. Package is dev-only (`[project.optional-dependencies].dev`), never distributed to PyPI.

## Complexity Tracking

No constitution violations requiring justification. This feature:
- Is internal tooling, not a platform component
- Uses standard patterns (Pydantic, structlog, pytest)
- Wraps external service (Cognee Cloud) rather than building custom infrastructure

## Implementation Phases

### Phase 1: Foundation (P0 User Stories)

**Goal**: Cognee Cloud connected, architecture docs indexed, basic search working.

**Deliverables**:
1. `devtools/agent-memory/` package structure
2. Configuration via environment variables + `.cognee/config.yaml`
3. `make cognee-init` for initial setup
4. `make cognee-health` for connection validation
5. Architecture documentation indexing
6. Basic search via CLI

**Dependencies**: Cognee Cloud account, OpenAI API key

### Phase 2: Automation (P1 User Stories)

**Goal**: Git hooks, MCP integration, docstring extraction.

**Deliverables**:
1. Post-commit hook for async sync
2. Post-merge hook for rebuild
3. MCP server configuration in `.claude/mcp.json`
4. Docstring extraction from Python packages
5. `make cognee-coverage` for coverage analysis

**Dependencies**: Phase 1 complete, git hook infrastructure

### Phase 3: Operations (P1 User Stories)

**Goal**: Full operational tooling suite.

**Deliverables**:
1. `make cognee-drift` for stale entry detection
2. `make cognee-repair` for selective repair
3. `make cognee-reset` for full reset (with confirmation)
4. `make cognee-test` for quality validation
5. Batch initial load with progress and resume

**Dependencies**: Phase 2 complete

### Phase 4: Session Recovery (P2 User Stories)

**Goal**: Cross-session context preservation.

**Deliverables**:
1. Session context capture
2. Session recovery protocol
3. Decision history queries
4. Capability index queries

**Dependencies**: Phase 3 complete

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cognee Cloud unavailable | LOW | MEDIUM | Health checks, retry logic, graceful degradation |
| API rate limits exceeded | MEDIUM | LOW | Batch processing, selective sync, local caching |
| Search quality insufficient | MEDIUM | MEDIUM | Quality validation suite, tuning search types |
| Hook performance impact | LOW | LOW | Async execution, background processing |
| Secret exposure | LOW | HIGH | Environment variables, SecretStr, gitignore |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Architecture query relevance | 90% within 3 attempts | Quality test suite |
| Search result accuracy | 95% for known queries | Quality test suite |
| Git hook latency | < 500ms added | Timing in hook scripts |
| Batch resume capability | 100% | Integration test |
| Coverage analysis accuracy | < 1% false positives | Integration test |
| Drift detection accuracy | 100% | Integration test |
