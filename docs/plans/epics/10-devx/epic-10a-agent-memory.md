# Epic 10A: Agent Memory (Cognee Integration)

## Summary

Cognee Cloud integration provides persistent, graph-augmented memory for Claude Code agents. This Epic establishes shared team knowledge graph for cross-session context preservation, decision traceability, and capability indexing, enhancing the developer experience and AI agent effectiveness across all developers and CI.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: TBD (to be created via /speckit.taskstolinear)

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

---

## Architecture References

### ADRs
- TBD: ADR-0046 - Agent Memory Architecture
- ADR-0042 - Linear + Beads Traceability (related)

### Interface Docs
- Cognee GitHub: https://github.com/topoteretes/cognee
- MCP Protocol: https://modelcontextprotocol.io/

### Contracts
- `CogneeClient` - Cognee Cloud API wrapper
- `CogneeSync` - Sync orchestration interface
- Knowledge graph ontology (entities, relationships for floe domain)

---

## File Ownership (Exclusive)

```text
packages/floe-devx/                    # New package
├── src/floe_devx/
│   ├── cognee_sync.py                 # Sync orchestration
│   ├── docstring_extractor.py         # Python docstring → graph
│   ├── markdown_parser.py             # Markdown → graph
│   └── mcp_server.py                  # MCP integration (thin wrapper)
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml

scripts/
├── setup-hooks.sh                     # Extended with Cognee hooks
└── cognee-sync                        # Sync CLI wrapper

.cognee/
├── config.yaml                        # Cognee Cloud configuration
└── .gitignore                         # Exclude credentials

.github/workflows/
└── cognee-sync.yml                    # CI sync workflow (optional)
```

**Note**: No Helm chart needed - using Cognee Cloud (SaaS).

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
**As a** platform developer
**I want** Cognee Cloud configured for the team
**So that** all agents share persistent memory

**Acceptance Criteria**:
- [ ] Cognee Cloud account created with team workspace
- [ ] API key configured in `.cognee/config.yaml` and GitHub secrets
- [ ] `cognee` client library added to `pyproject.toml`
- [ ] `make cognee-init` target for initial cognification
- [ ] Connection validation in CI pipeline

### US2: Architecture Documentation Indexing (P0)
**As a** platform developer
**I want** architecture docs automatically indexed
**So that** Claude Code can query architectural decisions

**Acceptance Criteria**:
- [ ] All 45 ADRs indexed with relationships
- [ ] Architecture docs (22,700+ lines) processed
- [ ] Constitution principles indexed
- [ ] Search returns relevant context for queries

### US3: Docstring Extraction (P1)
**As a** platform developer
**I want** Python docstrings extracted to knowledge graph
**So that** API surface is searchable and connected

**Acceptance Criteria**:
- [ ] Google-style docstrings parsed (Args, Returns, Raises)
- [ ] Class/method relationships captured
- [ ] Cross-references to architecture docs
- [ ] 100% class docstring, 95%+ function docstring coverage

### US4: Git Hook Integration (P1)
**As a** developer
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
**As a** developer returning after compaction
**I want** automatic context injection
**So that** I don't need to manually reconstruct state

**Acceptance Criteria**:
- [ ] Session state persisted to knowledge graph
- [ ] Previous session context retrieved at startup
- [ ] Related closed tasks suggested
- [ ] Decision history for current work available

---

## Technical Notes

### Key Decisions
- Use Cognee (graph-augmented RAG) over basic vector-only RAG
- **Cognee Cloud** (SaaS) - shared team knowledge, no infrastructure
- Async post-commit hooks (non-blocking)
- MCP integration (native Claude Code support)

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cloud dependency | LOW | MEDIUM | Cognee Cloud has SLA, data export available |
| API costs | MEDIUM | LOW | Batch processing, selective cognify |
| Hook performance | LOW | LOW | Async execution, don't block commits |
| Knowledge graph noise | MEDIUM | MEDIUM | Careful ontology design, validation |
| Secret management | LOW | MEDIUM | Use GitHub secrets, environment variables |

### Test Strategy
- **Unit**: `packages/floe-devx/tests/unit/`
  - Mock Cognee client for extraction tests
  - Test markdown/docstring parsing
  - Test hook scripts in isolation
- **Integration**: `packages/floe-devx/tests/integration/`
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
- `packages/*/src/` - Docstrings to extract
- `scripts/setup-hooks.sh` - Hook infrastructure

### Related Existing Code
- `scripts/setup-hooks.sh` - Chained hook pattern (extend)
- `.beads/` - Issue tracking (integrate decisions)
- `Makefile` - Build targets (add cognee-* targets)

### External Dependencies
- `cognee` (PyPI) - client library
- Cognee Cloud (SaaS) - https://cognee.ai - shared team knowledge graph
- OpenAI API (via Cognee) - for LLM processing during cognify
