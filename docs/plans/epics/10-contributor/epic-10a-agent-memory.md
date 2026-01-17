# Epic 10A: Agent Memory (Cognee Integration)

> **Audience**: AI coding agents (Claude Code, Cursor, etc.) and human maintainers
> **contributing to the floe codebase**.
>
> **Not For**: End users of floe, data engineers building pipelines, or platform engineers configuring floe.

## Summary

Cognee Cloud integration provides persistent, graph-augmented memory for **AI coding agents contributing to the floe codebase**. This Epic establishes shared knowledge graph for floe maintainers and AI assistants, enabling cross-session context preservation, decision traceability, and capability indexing.

## Status

- [x] Specification created
- [x] Tasks generated
- [x] Linear issues created
- [x] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: FLO (floe)

**Critical Bug Found (2026-01-16)**: API field name mismatch (`"data"` vs `"textData"`) caused
all synced content to be replaced with Cognee's default value. Code fixes applied; validation
and testing improvements tracked in [Epic 10B](./epic-10b-agent-memory-validation.md).

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| 10A-FR-001 | Cognee Cloud configuration and client setup | CRITICAL |
| 10A-FR-002 | Architecture docs cognification pipeline | CRITICAL |
| 10A-FR-003 | Docstring extraction and indexing | HIGH |
| 10A-FR-004 | Git hook integration (post-commit, post-merge) | HIGH |
| 10A-FR-005 | MCP server integration for Claude Code | HIGH |
| 10A-FR-006 | Session recovery protocol (automatic context injection) | MEDIUM |
| 10A-FR-007 | Decision register (searchable "why" history) | MEDIUM |
| 10A-FR-008 | Capability index ("have we solved this?") | MEDIUM |
| 10A-FR-009 | CI validation (coverage checks) | MEDIUM |
| 10A-FR-010 | Constitution/rules cross-reference | LOW |
| 10A-FR-011 | Linear/Beads sync bridging | LOW |
| 10A-FR-012 | Cognee Cloud configuration and secrets management | LOW |
| **Operations** |
| 10A-FR-013 | Batch initial load with progress tracking and resume | CRITICAL |
| 10A-FR-014 | Coverage analysis (indexed vs filesystem comparison) | HIGH |
| 10A-FR-015 | Drift detection (stale/orphaned entries) | HIGH |
| 10A-FR-016 | Quality validation test suite (known queries → expected results) | MEDIUM |
| 10A-FR-017 | Selective repair (re-index drifted content without full rebuild) | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0046](../../../architecture/adr/0046-agent-memory-architecture.md) - Agent Memory Architecture
- [ADR-0042](../../../architecture/adr/0042-linear-beads-traceability.md) - Linear + Beads Traceability (related)

### Interface Docs
- Cognee GitHub: https://github.com/topoteretes/cognee
- Cognee Documentation: https://docs.cognee.ai
- Cognee MCP Tools: https://docs.cognee.ai/cognee-mcp/mcp-tools
- Cognee HTTP API: https://docs.cognee.ai/http_api
- MCP Protocol: https://modelcontextprotocol.io/

### Contracts
- `CogneeClient` - Cognee Cloud API wrapper
- `CogneeSync` - Sync orchestration interface
- Knowledge graph ontology (entities, relationships for floe domain)

---

## File Ownership (Exclusive)

```text
devtools/                              # INTERNAL ONLY - never distributed
└── agent-memory/                      # Cognee integration for AI coding agents
    ├── pyproject.toml                 # "Private :: Do Not Upload" classifier
    ├── README.md                      # Explicit audience statement
    ├── src/agent_memory/
    │   ├── __init__.py
    │   ├── cli.py                     # CLI for Makefile targets
    │   ├── cognee_sync.py             # Sync orchestration
    │   ├── docstring_extractor.py     # Python docstring → graph
    │   ├── markdown_parser.py         # Markdown → graph
    │   ├── mcp_server.py              # MCP integration (thin wrapper)
    │   ├── ops/                       # Operational tooling
    │   │   ├── __init__.py
    │   │   ├── health.py              # Health check wrapper
    │   │   ├── coverage.py            # Indexed vs filesystem analysis
    │   │   ├── drift.py               # Stale entry detection
    │   │   ├── batch.py               # Batch load with checkpoints
    │   │   └── quality.py             # Search quality validation
    │   └── checkpoints/               # Resume state for batch operations
    │       └── .gitignore
    └── tests/
        ├── unit/
        ├── integration/
        └── quality/                   # Known query → expected result tests
            └── test_search_quality.py

scripts/
├── setup-hooks.sh                     # Extended with Cognee hooks
└── cognee-sync                        # Sync CLI wrapper

.cognee/
├── config.yaml                        # Cognee Cloud configuration
├── checksums.json                     # Content hashes for drift detection
└── .gitignore                         # Exclude credentials

.github/workflows/
└── cognee-sync.yml                    # CI sync workflow (optional)
```

**Note**: No Helm chart needed - using Cognee Cloud (SaaS). Package is dev-only via `[project.optional-dependencies].dev`.

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | 9C | Uses K8s-native testing patterns |
| Blocked By | None (optional) | Can proceed independently |
| Blocks | None | Enhancement, not blocking |
| Related | 6A | OpenTelemetry for graph query tracing |

**Note**: This Epic is **non-blocking** - it enhances developer experience but doesn't gate other platform functionality.

---

## User Stories (for SpecKit)

### US1: Cognee Cloud Setup (P0)
**As a** floe contributor (human or AI agent)
**I want** Cognee Cloud configured for the team
**So that** all agents share persistent memory

**Acceptance Criteria**:
- [ ] Cognee Cloud account created with team workspace
- [ ] API key configured in `.cognee/config.yaml` and GitHub secrets
- [ ] `cognee` client library added to `pyproject.toml`
- [ ] `make cognee-init` target for initial cognification
- [ ] Connection validation in CI pipeline

### US2: Architecture Documentation Indexing (P0)
**As a** floe contributor (human or AI agent)
**I want** architecture docs automatically indexed
**So that** Claude Code can query architectural decisions

**Acceptance Criteria**:
- [ ] All 45 ADRs indexed with relationships
- [ ] Architecture docs (22,700+ lines) processed
- [ ] Constitution principles indexed
- [ ] Search returns relevant context for queries

### US3: Docstring Extraction (P1)
**As a** floe contributor (human or AI agent)
**I want** Python docstrings extracted to knowledge graph
**So that** API surface is searchable and connected

**Acceptance Criteria**:
- [ ] Google-style docstrings parsed (Args, Returns, Raises)
- [ ] Class/method relationships captured
- [ ] Cross-references to architecture docs
- [ ] 100% class docstring, 95%+ function docstring coverage

### US4: Git Hook Integration (P1)
**As a** floe contributor
**I want** knowledge graph updated automatically
**So that** memory stays current without manual sync

**Acceptance Criteria**:
- [ ] post-commit hook syncs changed files (async)
- [ ] post-merge hook triggers full rebuild
- [ ] pre-push hook validates coverage (optional)
- [ ] Hooks don't block developer workflow

### US5: MCP Server Integration (P1)
**As a** Claude Code agent
**I want** to query Cognee via MCP
**So that** I can access persistent memory during sessions

**Acceptance Criteria**:
- [ ] Cognee MCP server configured in `.claude/mcp.json`
- [ ] `cognify`, `search`, `codify` tools available
- [ ] Session context query on session start
- [ ] Decision history queryable

### US6: Session Recovery Protocol (P2)
**As a** floe contributor (or AI agent) returning after compaction
**I want** automatic context injection
**So that** I don't need to manually reconstruct state

**Acceptance Criteria**:
- [ ] Session state persisted to knowledge graph
- [ ] Previous session context retrieved at startup
- [ ] Related closed tasks suggested
- [ ] Decision history for current work available

### US7: Operational Management (P1)
**As a** floe maintainer
**I want** operational tools to manage the knowledge graph
**So that** I can diagnose issues, recover from failures, and ensure data quality

**Acceptance Criteria**:
- [ ] `make cognee-health` checks connection and component status
- [ ] `make cognee-init` performs batch initial load with progress and resume
- [ ] `make cognee-coverage` reports indexed vs filesystem diff
- [ ] `make cognee-drift` detects stale/orphaned entries
- [ ] `make cognee-repair` selectively re-indexes drifted content
- [ ] `make cognee-reset` performs full wipe and rebuild (with confirmation)
- [ ] `make cognee-test` runs quality validation suite
- [ ] All operations are idempotent and safe to retry

---

## Technical Notes

### Key Decisions
- Use Cognee (graph-augmented RAG) over basic vector-only RAG
- **Cognee Cloud** (SaaS) - shared team knowledge, no infrastructure
- Async post-commit hooks (non-blocking)
- MCP integration (native Claude Code support)

### Cognee Built-in Capabilities (Use Directly)

Cognee provides these operations out of the box - we wrap, not rebuild:

| Capability | Cognee API | Notes |
|------------|-----------|-------|
| Health check | `GET /health/detailed` | Component-level status |
| Full reset | `prune_system(graph, vector, metadata, cache)` | Granular control |
| Delete data | `delete` MCP tool, `DELETE /api/v1/datasets/{id}` | Soft/hard modes |
| List datasets | `list_data` MCP tool | Enumerate all content |
| Pipeline status | `cognify_status`, `codify_status` | Track long-running jobs |
| Settings | `GET/POST /api/v1/settings` | Configuration management |
| Visualization | `GET /api/v1/datasets/{id}/graph` | HTML graph view |

**MCP Tools** (11 available): `cognify`, `codify`, `search`, `prune`, `delete`, `list_data`, `cognify_status`, `codify_status`, `save_interaction`, `get_developer_rules`, `cognee_add_developer_rules`

### What We Build (On Top of Cognee)

| Capability | Why Cognee Can't | Our Implementation |
|------------|------------------|-------------------|
| Coverage analysis | No filesystem awareness | Compare `list_data` to glob results |
| Drift detection | No rename/delete tracking | Hash-based content tracking |
| Batch initial load | Per-dataset only | Iterator with progress + checkpoints |
| Quality validation | No test suite concept | Known queries → expected results |
| Selective repair | Prune is all-or-nothing | Delete stale + add missing only |

### Operational Procedures

#### Makefile Targets

```makefile
# Cognee-native (thin wrappers)
make cognee-health      # GET /health/detailed + connection test
make cognee-status      # cognify_status + codify_status
make cognee-reset       # prune_system(all=True) ⚠️ DESTRUCTIVE

# Our additions (build on Cognee)
make cognee-init        # Batch load: progress, checkpoints, resume
make cognee-coverage    # Report: indexed vs should-be-indexed
make cognee-drift       # Detect stale entries (deleted/renamed files)
make cognee-repair      # Delete stale + re-index missing (no full rebuild)
make cognee-test        # Quality validation: known queries → expected results
```

#### Recovery Runbook

**Scenario: Search returns garbage / corruption suspected**
```bash
make cognee-health       # Check component status
make cognee-test         # Run quality validation
make cognee-drift        # Check for stale entries
make cognee-repair       # Try selective repair first
# If still broken:
make cognee-reset        # Nuclear option: full wipe + rebuild
make cognee-test         # Verify recovery
```

**Scenario: Batch process failed mid-way**
```bash
make cognee-coverage     # See what's indexed vs missing
make cognee-init         # Resume from checkpoint (idempotent)
make cognee-coverage     # Verify completion
```

**Scenario: Files renamed/deleted but still in graph**
```bash
make cognee-drift        # Detect orphaned entries
make cognee-repair       # Remove stale + add new paths
```

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cloud dependency | LOW | MEDIUM | Cognee Cloud has SLA, data export available |
| API costs | MEDIUM | LOW | Batch processing, selective cognify |
| Hook performance | LOW | LOW | Async execution, don't block commits |
| Knowledge graph noise | MEDIUM | MEDIUM | Careful ontology design, validation |
| Secret management | LOW | MEDIUM | Use GitHub secrets, environment variables |

### Test Strategy
- **Unit**: `devtools/agent-memory/tests/unit/`
  - Mock Cognee client for extraction tests
  - Test markdown/docstring parsing
  - Test hook scripts in isolation
- **Integration**: `devtools/agent-memory/tests/integration/`
  - Real Cognee Cloud API (test workspace)
  - Full cognify → search cycle
  - Validate search quality with known docs
- **E2E**: `tests/e2e/test_session_recovery.py`
  - Simulate compaction → recovery cycle
  - Validate context injection quality

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/architecture/` - 22,700+ lines to index
- `.specify/memory/constitution.md` - Core principles
- `.claude/rules/` - Enforcement rules
- `.claude/skills/` - 13 skills to index
- `packages/*/src/`, `plugins/*/src/` - Docstrings to extract
- `scripts/setup-hooks.sh` - Hook infrastructure
- `devtools/agent-memory/` - This Epic's implementation

### Related Existing Code
- `scripts/setup-hooks.sh` - Chained hook pattern (extend)
- `.beads/` - Issue tracking (integrate decisions)
- `Makefile` - Build targets (add cognee-* targets)

### External Dependencies
- `cognee` (PyPI) - client library
- Cognee Cloud (SaaS) - https://cognee.ai - shared team knowledge graph
- OpenAI API (via Cognee) - for LLM processing during cognify
