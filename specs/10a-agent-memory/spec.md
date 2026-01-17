# Feature Specification: Agent Memory (Cognee Integration)

**Epic**: 10A (Agent Memory - Cognee Integration)
**Feature Branch**: `10a-agent-memory`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "docs/plans/epics/10-contributor/epic-10a-agent-memory.md"

> **Audience**: AI coding agents (Claude Code, Cursor, etc.) and human maintainers contributing to the floe codebase.
>
> **Not For**: End users of floe, data engineers building pipelines, or platform engineers configuring floe.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cognee Cloud Setup (Priority: P0)

As a floe contributor (human or AI agent), I want Cognee Cloud configured for the team so that all agents share persistent memory across sessions.

**Why this priority**: Foundation - without cloud configuration, no other features can work. This is the prerequisite for all knowledge graph functionality.

**Independent Test**: Can be fully tested by verifying API connectivity and running a simple cognify/search cycle. Delivers immediate value: shared team knowledge store operational.

**Acceptance Scenarios**:

1. **Given** a fresh installation with API credentials configured, **When** the connection test runs, **Then** it confirms successful authentication with Cognee Cloud workspace
2. **Given** configured credentials in environment variables, **When** initial setup command executes, **Then** the system connects to the team workspace without errors
3. **Given** invalid or missing credentials, **When** connection is attempted, **Then** clear error messages indicate the specific credential issue

---

### User Story 2 - Architecture Documentation Indexing (Priority: P0)

As a floe contributor (human or AI agent), I want architecture docs automatically indexed so that queries return relevant architectural context and decisions.

**Why this priority**: Critical - architecture docs (ADRs, design decisions, principles) are the most valuable knowledge for maintaining consistency across AI agent sessions. Without this, agents lose architectural context after compaction.

**Independent Test**: Can be tested by indexing architecture docs and running queries for known architectural decisions. Delivers immediate value: searchable architectural knowledge.

**Acceptance Scenarios**:

1. **Given** architecture docs exist in the repository, **When** initial indexing runs, **Then** all ADRs and architecture documents are processed and searchable
2. **Given** indexed architecture documentation, **When** a contributor queries "plugin system design", **Then** relevant ADRs and design documents are returned
3. **Given** indexed constitution principles, **When** a contributor queries a governance question, **Then** relevant constitution rules are surfaced

---

### User Story 3 - Docstring Extraction (Priority: P1)

As a floe contributor (human or AI agent), I want Python docstrings extracted to the knowledge graph so that the API surface is searchable and connected to architecture.

**Why this priority**: High value - connects implementation documentation to architectural decisions, enabling contributors to understand "how" relates to "why".

**Independent Test**: Can be tested by extracting docstrings from a package and querying for function/class information. Delivers value: searchable codebase documentation.

**Acceptance Scenarios**:

1. **Given** Python source files with Google-style docstrings, **When** extraction runs, **Then** class and function documentation is indexed with relationships preserved
2. **Given** indexed docstrings, **When** a contributor searches for a capability, **Then** relevant functions and classes are returned with their documentation
3. **Given** indexed docstrings and architecture docs, **When** a contributor queries, **Then** cross-references between code and architecture are visible

---

### User Story 4 - Git Hook Integration (Priority: P1)

As a floe contributor, I want the knowledge graph updated automatically so that memory stays current without manual sync operations.

**Why this priority**: Automation - without automatic updates, the knowledge graph becomes stale. This ensures ongoing value without contributor effort.

**Independent Test**: Can be tested by making a commit with changed files and verifying the knowledge graph updates. Delivers value: self-maintaining knowledge.

**Acceptance Scenarios**:

1. **Given** git hooks are installed, **When** a developer commits changes, **Then** changed files are queued for asynchronous sync without blocking the commit
2. **Given** git hooks are installed, **When** a developer merges a branch, **Then** a comprehensive rebuild is triggered in the background
3. **Given** a sync is in progress, **When** a developer attempts to commit, **Then** the commit proceeds immediately without waiting

---

### User Story 5 - MCP Server Integration (Priority: P1)

As a Claude Code agent, I want to query the knowledge graph via MCP so that I can access persistent memory during coding sessions.

**Why this priority**: Core capability - MCP is the interface that enables AI agents to leverage the knowledge graph during their work.

**Independent Test**: Can be tested by configuring MCP and issuing search queries from Claude Code. Delivers value: AI agent memory access.

**Acceptance Scenarios**:

1. **Given** MCP server is configured, **When** Claude Code starts, **Then** Cognee tools (cognify, search, codify) are available
2. **Given** an active Claude Code session, **When** the agent searches for prior decisions, **Then** relevant decision history is returned
3. **Given** session context exists in the knowledge graph, **When** a session starts, **Then** relevant prior context can be retrieved

---

### User Story 6 - Session Recovery (Priority: P2)

As a floe contributor (or AI agent) returning after compaction, I want automatic context injection so that I don't need to manually reconstruct working state.

**Why this priority**: Medium - enhances productivity but not essential for basic memory functionality.

**Independent Test**: Can be tested by simulating session end/start and verifying context recovery. Delivers value: seamless session continuity.

**Acceptance Scenarios**:

1. **Given** a previous session with tracked work, **When** a new session starts, **Then** the previous session's context is available for retrieval
2. **Given** closed tasks related to current work, **When** session recovery runs, **Then** relevant completed work is suggested
3. **Given** decision history for current work area, **When** session recovery runs, **Then** prior decisions are accessible

---

### User Story 7 - Operational Management (Priority: P1)

As a floe maintainer, I want operational tools to manage the knowledge graph so that I can diagnose issues, recover from failures, and ensure data quality.

**Why this priority**: High - operational tooling is essential for production reliability. Without it, issues cannot be diagnosed or resolved.

**Independent Test**: Can be tested by running each operational command and verifying expected output. Delivers value: maintainable system.

**Acceptance Scenarios**:

1. **Given** the system is running, **When** health check executes, **Then** component status is reported (connection, graph, vector store)
2. **Given** a partial initial load, **When** batch load resumes, **Then** processing continues from checkpoint without reprocessing completed items
3. **Given** files have been renamed or deleted, **When** drift detection runs, **Then** stale/orphaned entries are identified
4. **Given** drifted entries exist, **When** selective repair runs, **Then** only stale entries are removed and missing entries added (no full rebuild)
5. **Given** the system is operational, **When** quality validation runs, **Then** known queries return expected results

---

### Edge Cases

- What happens when Cognee Cloud is temporarily unavailable during a sync?
- How does the system handle files that exceed size limits for indexing?
- What happens when docstring parsing encounters malformed docstrings?
- How does the system handle concurrent sync operations (multiple developers committing)?
- What happens when batch initial load is interrupted mid-way?
- How does the system handle renamed files (same content, different path)?
- What happens when search returns no results for a valid query?
- How does the system handle circular dependencies in the knowledge graph?

## Requirements *(mandatory)*

### Functional Requirements

**Configuration & Setup**
- **FR-001**: System MUST provide a configuration mechanism for Cognee Cloud credentials without hardcoding secrets
- **FR-002**: System MUST validate connection to Cognee Cloud workspace before operations
- **FR-003**: System MUST provide a setup command that initializes the knowledge graph for first-time use

**Content Indexing**
- **FR-004**: System MUST index all architecture documentation files (ADRs, design docs)
- **FR-005**: System MUST index constitution principles and enforcement rules
- **FR-006**: System MUST parse and index Python docstrings in Google-style format
- **FR-007**: System MUST capture class and method relationships from docstrings
- **FR-008**: System MUST support cross-references between code documentation and architecture docs

**Automation**
- **FR-009**: System MUST provide git hooks that trigger sync on post-commit events
- **FR-010**: System MUST provide git hooks that trigger rebuild on post-merge events
- **FR-011**: Git hooks MUST NOT block developer workflow (asynchronous execution)
- **FR-012**: System MUST track which files need sync based on git changes

**Query Interface**
- **FR-013**: System MUST expose search capability via MCP protocol for Claude Code
- **FR-014**: System MUST support querying decision history (why questions)
- **FR-015**: System MUST support querying capability index (have we solved this before?)
- **FR-016**: System MUST support session context retrieval for session recovery

**Operational Tooling**
- **FR-017**: System MUST provide health check command showing component status
- **FR-018**: System MUST provide batch initial load with progress tracking and resume capability
- **FR-019**: System MUST provide coverage analysis comparing indexed content to filesystem
- **FR-020**: System MUST provide drift detection for stale/orphaned entries
- **FR-021**: System MUST provide selective repair without requiring full rebuild
- **FR-022**: System MUST provide full reset capability with confirmation safeguard
- **FR-023**: System MUST provide quality validation testing known queries against expected results
- **FR-024**: All operational commands MUST be idempotent and safe to retry

### Key Entities

- **Knowledge Graph Entry**: Represents indexed content (document, docstring, decision) with metadata (source path, content hash, timestamp, relationships)
- **Sync State**: Tracks which files have been indexed, their content hashes, and last sync timestamp
- **Checkpoint**: Resume point for batch operations, tracking progress through large indexing jobs
- **Search Result**: Query response containing relevant content, source references, and confidence/relevance score
- **Session Context**: Captured working state including active work areas, recent decisions, and related closed tasks

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Contributors can find relevant architectural context within 3 query attempts for 90% of common questions
- **SC-002**: Knowledge graph search returns relevant results for 95% of known-good test queries
- **SC-003**: Initial indexing of all architecture docs (45+ ADRs, 22,700+ lines) completes successfully
- **SC-004**: Git hook sync operations do not add measurable delay to commit/push workflow (< 500ms added latency)
- **SC-005**: Batch operations can resume after interruption without reprocessing completed items
- **SC-006**: Coverage analysis accurately reports indexed vs. filesystem state with < 1% false positives
- **SC-007**: Drift detection identifies 100% of renamed/deleted files that remain in the graph
- **SC-008**: Health check accurately reports component status for troubleshooting
- **SC-009**: Session recovery provides useful prior context for 80% of resumed work sessions
- **SC-010**: 100% class docstring coverage and 95%+ function docstring coverage is maintained
