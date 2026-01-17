# Tasks: Agent Memory (Cognee Integration)

**Input**: Design documents from `/specs/10a-agent-memory/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Integration tests included for critical paths (Cognee Cloud API, sync cycle, search quality).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This feature uses a single package in `devtools/agent-memory/` following the Epic 10A file ownership specification.

---

## Phase 1: Setup (Project Structure)

**Purpose**: Create the devtools/agent-memory package structure with proper Python packaging.

- [ ] T001 Create `devtools/agent-memory/` directory structure per plan.md
- [ ] T002 Create `devtools/agent-memory/pyproject.toml` with:
  - Package name: `agent-memory`
  - Classifier: `"Private :: Do Not Upload"`
  - Dependencies: `cognee>=0.5.0`, `cognee-mcp>=0.5.0`, `httpx>=0.27.0`, `structlog`, `pydantic>=2.0`, `typer>=0.9.0`
  - Entry point: `agent-memory = agent_memory.cli:app`
- [ ] T003 [P] Create `devtools/agent-memory/README.md` with explicit audience statement (floe contributors only)
- [ ] T004 [P] Create `devtools/agent-memory/src/agent_memory/__init__.py` with `__version__ = "0.1.0"`
- [ ] T005 [P] Create `.cognee/.gitignore` with entries: `config.yaml`, `state.json`, `checksums.json`, `*.log`

**Checkpoint**: Package structure ready for implementation

---

## Phase 2: Foundational (Config & Client)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### Configuration Models

- [ ] T006 Create `devtools/agent-memory/src/agent_memory/config.py` with:
  - `AgentMemoryConfig` Pydantic model per data-model.md
  - `ContentSource` model for source path patterns
  - Load from `.cognee/config.yaml` with `pydantic-settings`
  - Environment variable support: `COGNEE_API_KEY`, `OPENAI_API_KEY`
  - SecretStr for API keys
- [ ] T007 [P] Create `devtools/agent-memory/src/agent_memory/models.py` with:
  - `SyncState` model (last_sync_time, datasets, files_indexed)
  - `FileChecksum` model (path, sha256, last_modified, indexed_at)
  - `BatchCheckpoint` model (operation_id, current_index, total_items, started_at)
  - `SearchResult` model (query, results, search_type, duration_ms)
  - `HealthStatus` model per data-model.md

### Cognee Client Wrapper

- [ ] T008 Create `devtools/agent-memory/src/agent_memory/cognee_client.py` with:
  - `CogneeClient` class wrapping async Cognee SDK
  - Methods: `add_content()`, `cognify()`, `codify()`, `search()`, `delete()`, `list_datasets()`
  - Configure from `AgentMemoryConfig`
  - Use `httpx` for health check API calls
  - Structured logging with `structlog`
  - Error handling with retry logic for transient failures

### CLI Foundation

- [ ] T009 Create `devtools/agent-memory/src/agent_memory/cli.py` with:
  - Typer app structure
  - Subcommands: `init`, `sync`, `search`, `health`, `coverage`, `drift`, `repair`, `reset`, `test`
  - Load config on startup
  - Async execution wrapper (`asyncio.run()`)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1+2 - Cognee Cloud Setup + Architecture Indexing (Priority: P0)

**Goal**: Cognee Cloud connected, architecture docs indexed, basic search working.

**Independent Test**: Run `make cognee-health` to verify connection, then `make cognee-search QUERY="plugin system"` to verify indexing.

### Tests for US1+US2

- [ ] T010 [P] [US1] Create `devtools/agent-memory/tests/integration/test_cognee_cloud.py` with:
  - `test_health_check_returns_healthy()` - verify API connectivity
  - `test_authentication_with_valid_credentials()` - verify team workspace access
  - `test_authentication_fails_with_invalid_credentials()` - verify clear error messages
  - Use `@pytest.mark.requirement("FR-001", "FR-002")`
- [ ] T011 [P] [US2] Create `devtools/agent-memory/tests/integration/test_sync_cycle.py` with:
  - `test_cognify_architecture_docs()` - index sample ADR, verify searchable
  - `test_search_returns_relevant_results()` - query "plugin system", expect ADR-0001
  - Use `@pytest.mark.requirement("FR-004", "FR-005")`

### Implementation for US1 (Cognee Cloud Setup)

- [ ] T012 [US1] Implement `health` command in `cli.py`:
  - Call Cognee Cloud `/health/detailed` endpoint via `httpx`
  - Parse `HealthStatus` response
  - Display component status (relational_db, vector_db, graph_db, llm_provider)
  - Return exit code 0 if healthy, 1 if degraded/unhealthy
- [ ] T013 [US1] Add connection validation to `CogneeClient.__init__()`:
  - Call health check on initialization
  - Raise `ConnectionError` with clear message if unreachable
  - Log connection latency
- [ ] T014 [US1] Create `Makefile` targets in repository root:
  - `cognee-health`: Run health check
  - `cognee-init`: Initial setup with `--setup` flag
  - Include `COGNEE_API_KEY` and `OPENAI_API_KEY` environment variable checks

### Implementation for US2 (Architecture Documentation Indexing)

- [ ] T015 [US2] Create `devtools/agent-memory/src/agent_memory/markdown_parser.py` with:
  - `parse_markdown_file(path: Path) -> ParsedContent` function
  - Extract title, headers, content sections
  - Preserve frontmatter metadata (YAML)
  - Return `ParsedContent` with `title`, `content`, `metadata`, `source_path`
- [ ] T016 [US2] Implement `init` command in `cli.py`:
  - Load sources from config
  - For each source matching architecture pattern (`docs/architecture/**/*.md`):
    - Parse markdown content
    - Call `cognee.add()` with dataset="architecture"
  - Call `cognee.cognify(datasets=["architecture"])`
  - Display progress (current/total files)
  - Save `SyncState` to `.cognee/state.json`
- [ ] T017 [US2] Implement `search` command in `cli.py`:
  - Accept `--query` argument (required)
  - Accept `--type` argument (default: `GRAPH_COMPLETION`)
  - Accept `--dataset` argument (optional, filter by dataset)
  - Call `cognee.search()` with parameters
  - Display results with source references
- [ ] T018 [US2] Add Makefile targets:
  - `cognee-init`: Full initial load with progress
  - `cognee-init PROGRESS=1`: Show progress bar
  - `cognee-init RESUME=1`: Resume from checkpoint
  - `cognee-search QUERY="..."`: Search command

**Checkpoint**: US1 (Cognee Cloud Setup) and US2 (Architecture Indexing) fully functional

---

## Phase 4: User Story 3 - Docstring Extraction (Priority: P1)

**Goal**: Python docstrings extracted and searchable in the knowledge graph.

**Independent Test**: Run `make cognee-search QUERY="CogneeClient" TYPE=CODE` to find class docstrings.

### Tests for US3

- [ ] T019 [P] [US3] Create `devtools/agent-memory/tests/unit/test_docstring_extractor.py` with:
  - `test_extract_class_docstring()` - verify class doc extraction
  - `test_extract_method_docstring()` - verify method doc extraction
  - `test_extract_google_style_docstring()` - verify Args/Returns parsing
  - `test_handle_malformed_docstring()` - verify graceful handling
  - Use `@pytest.mark.requirement("FR-006", "FR-007")`

### Implementation for US3

- [ ] T020 [US3] Create `devtools/agent-memory/src/agent_memory/docstring_extractor.py` with:
  - `extract_docstrings(path: Path) -> list[DocstringEntry]` function
  - Use `ast` module to parse Python files
  - Extract class docstrings with class name, bases, methods
  - Extract function/method docstrings with signature
  - Parse Google-style format (Args, Returns, Raises, Examples)
  - Return `DocstringEntry` with `name`, `type`, `docstring`, `source_path`, `line_number`
- [ ] T021 [US3] Implement `codify` subcommand in `cli.py`:
  - Load Python source patterns from config (`packages/*/src/**/*.py`)
  - For each Python file:
    - Extract docstrings using `docstring_extractor`
    - Call `cognee.codify()` with dataset="codebase"
  - Display progress
  - Update `SyncState` with indexed files
- [ ] T022 [US3] Add Makefile target:
  - `cognee-codify`: Extract and index all Python docstrings
  - `cognee-codify FILES="..."`: Index specific files

**Checkpoint**: US3 (Docstring Extraction) fully functional

---

## Phase 5: User Story 4 - Git Hook Integration (Priority: P1)

**Goal**: Knowledge graph automatically updated on commits without blocking workflow.

**Independent Test**: Make a test commit with a changed ADR, verify it appears in search within 30 seconds.

### Implementation for US4

- [ ] T023 [US4] Create `scripts/cognee-sync` wrapper script:
  - Accept `--files` argument for specific files
  - Accept `--async` flag for background execution
  - Call `agent-memory sync` CLI command
  - Log to `.cognee/sync.log`
- [ ] T024 [US4] Create `devtools/agent-memory/src/agent_memory/git_diff.py` with:
  - `get_changed_files(since: str = "HEAD~1") -> list[Path]` function
  - Use `git diff --name-only` to detect changes
  - Filter to configured source patterns
  - Return list of changed file paths
- [ ] T025 [US4] Implement `sync` command in `cli.py`:
  - Accept `--files` argument (optional, specific files)
  - Accept `--all` flag (sync all, not just changed)
  - Accept `--dry-run` flag (report what would sync)
  - If no files specified, detect from git diff
  - For each changed file:
    - If markdown: parse and `cognee.add()`
    - If Python: extract docstrings and `cognee.codify()`
  - Call `cognee.cognify()` for affected datasets
  - Update `SyncState` and file checksums
- [ ] T026 [US4] Update `scripts/setup-hooks.sh` to add Cognee hooks:
  - Add `post-commit` hook: `scripts/cognee-sync --async`
  - Add `post-merge` hook: `scripts/cognee-sync --all --async`
  - Hooks must be non-blocking (background execution)
- [ ] T027 [US4] Add Makefile targets:
  - `cognee-sync`: Sync changed files
  - `cognee-sync FILES="..."`: Sync specific files
  - `cognee-sync DRY_RUN=1`: Dry run mode
  - `setup-hooks`: Install git hooks including Cognee

**Checkpoint**: US4 (Git Hook Integration) fully functional

---

## Phase 6: User Story 5 - MCP Server Integration (Priority: P1)

**Goal**: Claude Code can query knowledge graph via MCP tools during sessions.

**Independent Test**: Start MCP server, configure Claude Code, run search query in Claude Code session.

### Implementation for US5

- [ ] T028 [US5] Create `devtools/agent-memory/src/agent_memory/mcp_config.py` with:
  - `generate_mcp_config() -> dict` function
  - Return MCP server configuration for `.claude/mcp.json`
  - Include `transport: "http"`, `url: "http://localhost:8000/mcp"`
- [ ] T029 [US5] Implement `mcp-config` subcommand in `cli.py`:
  - Generate MCP configuration JSON
  - Optionally update `.claude/mcp.json` with `--install` flag
  - Display configuration for manual setup
- [ ] T030 [US5] Create `scripts/cognee-mcp-start` script:
  - Start Cognee MCP Docker container
  - Pass environment variables: `TRANSPORT_MODE`, `LLM_API_KEY`, `API_URL`, `API_TOKEN`
  - Map port 8000
  - Use `--rm -it` for clean execution
- [ ] T031 [US5] Add Makefile targets:
  - `cognee-mcp-start`: Start MCP server via Docker
  - `cognee-mcp-stop`: Stop MCP server
  - `cognee-mcp-config`: Generate MCP configuration
- [ ] T032 [US5] Update `quickstart.md` Section 7 with:
  - MCP server configuration steps
  - Claude Code integration instructions
  - Available MCP tools reference

**Checkpoint**: US5 (MCP Server Integration) fully functional

---

## Phase 7: User Story 7 - Operational Management (Priority: P1)

**Goal**: Full operational tooling suite for maintainability.

**Independent Test**: Run each operational command and verify expected output.

### Tests for US7

- [ ] T033 [P] [US7] Create `devtools/agent-memory/tests/unit/test_ops_coverage.py` with:
  - `test_coverage_report_accuracy()` - verify filesystem vs indexed comparison
  - `test_coverage_handles_missing_files()` - verify missing file detection
  - Use `@pytest.mark.requirement("FR-019")`
- [ ] T034 [P] [US7] Create `devtools/agent-memory/tests/unit/test_ops_drift.py` with:
  - `test_drift_detects_deleted_files()` - verify deleted file detection
  - `test_drift_detects_renamed_files()` - verify renamed file detection
  - Use `@pytest.mark.requirement("FR-020")`

### Implementation for US7

- [ ] T035 [US7] Create `devtools/agent-memory/src/agent_memory/ops/__init__.py`
- [ ] T036 [US7] Create `devtools/agent-memory/src/agent_memory/ops/health.py` with:
  - `health_check() -> HealthStatus` function
  - Call Cognee Cloud health endpoint
  - Parse component status
  - Return structured `HealthStatus`
- [ ] T037 [US7] Create `devtools/agent-memory/src/agent_memory/ops/coverage.py` with:
  - `analyze_coverage() -> CoverageReport` function
  - Glob filesystem for configured source patterns
  - Call `cognee.list_datasets()` to get indexed files
  - Compare and report: total files, indexed files, coverage percentage, missing files
- [ ] T038 [US7] Create `devtools/agent-memory/src/agent_memory/ops/drift.py` with:
  - `detect_drift() -> DriftReport` function
  - Load file checksums from `.cognee/checksums.json`
  - Compare current filesystem hashes to stored hashes
  - Detect: stale (content changed), orphaned (deleted), renamed (same hash, different path)
  - Return `DriftReport` with categorized entries
- [ ] T039 [US7] Create `devtools/agent-memory/src/agent_memory/ops/batch.py` with:
  - `batch_load(sources: list[ContentSource], progress_callback) -> BatchResult` function
  - Load files in batches (batch_size from config)
  - Save checkpoints to `.cognee/checkpoint.json` after each batch
  - Support resume from checkpoint
  - Report progress via callback
- [ ] T040 [US7] Create `devtools/agent-memory/src/agent_memory/ops/quality.py` with:
  - `validate_quality(test_queries: list[TestQuery]) -> QualityReport` function
  - Define known query → expected result pairs
  - Execute each query, verify expected results appear
  - Report pass/fail for each test query
- [ ] T041 [US7] Implement `coverage` command in `cli.py`:
  - Call `analyze_coverage()`
  - Display: total files, indexed files, coverage percentage
  - List missing files if verbose
- [ ] T042 [US7] Implement `drift` command in `cli.py`:
  - Call `detect_drift()`
  - Display categorized drift entries (stale, orphaned, renamed)
  - Accept `--format` argument (table, json)
- [ ] T043 [US7] Implement `repair` command in `cli.py`:
  - Accept `--dry-run` flag
  - Call `detect_drift()` to get drift report
  - For stale entries: delete and re-add
  - For orphaned entries: delete only
  - For renamed entries: update path metadata (or delete + re-add)
  - Update `SyncState` and checksums
- [ ] T044 [US7] Implement `reset` command in `cli.py`:
  - Require `--confirm` flag (safety)
  - Call `cognee.prune_system(graph=True, vector=True, metadata=True, cache=True)`
  - Delete `.cognee/state.json` and `.cognee/checksums.json`
  - Display confirmation message
- [ ] T045 [US7] Implement `test` subcommand in `cli.py`:
  - Define known test queries in config or hardcoded
  - Call `validate_quality()`
  - Display pass/fail for each query
  - Return exit code based on pass rate
- [ ] T046 [US7] Add Makefile targets:
  - `cognee-coverage`: Coverage analysis
  - `cognee-drift`: Drift detection
  - `cognee-repair`: Repair drifted entries
  - `cognee-reset CONFIRM=1`: Full reset
  - `cognee-test`: Quality validation

**Checkpoint**: US7 (Operational Management) fully functional

---

## Phase 8: User Story 6 - Session Recovery (Priority: P2)

**Goal**: Cross-session context preservation for AI agents.

**Independent Test**: End a session with active work, start new session, verify prior context available.

### Implementation for US6

- [ ] T047 [US6] Create `devtools/agent-memory/src/agent_memory/session.py` with:
  - `SessionContext` model per data-model.md
  - `capture_session_context(active_issues: list[str], decisions: list[str]) -> SessionContext` function
  - `save_session_context(context: SessionContext)` - store via `cognee.add()`
  - `retrieve_session_context(work_area: str) -> SessionContext | None` - query via `cognee.search()`
- [ ] T048 [US6] Implement `session-save` subcommand in `cli.py`:
  - Accept `--issues` argument (comma-separated issue IDs)
  - Accept `--decisions` argument (comma-separated decision descriptions)
  - Capture and save session context
- [ ] T049 [US6] Implement `session-recover` subcommand in `cli.py`:
  - Accept `--work-area` argument (topic to recover context for)
  - Query knowledge graph for relevant prior sessions
  - Display: prior work, closed tasks, decision history
- [ ] T050 [US6] Integrate with Beads `bd prime` command:
  - Add hook in `bd prime` to call `session-recover`
  - Inject recovered context into session start

**Checkpoint**: US6 (Session Recovery) fully functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation.

- [ ] T051 [P] Create `devtools/agent-memory/tests/conftest.py` with shared fixtures:
  - `config_fixture`: Load test configuration
  - `cognee_client_fixture`: Configured CogneeClient (mock for unit, real for integration)
  - `temp_content_dir`: Temporary directory with sample content
- [ ] T052 [P] Create `devtools/agent-memory/tests/quality/test_search_quality.py` with:
  - `test_known_queries_return_expected_results()` - quality validation suite
  - Define 10+ known query → expected result pairs
  - Use `@pytest.mark.requirement("SC-002")`
- [ ] T053 Run full test suite and fix any failures
- [ ] T054 Run `make cognee-init` on full repository and verify coverage
- [ ] T055 Run `make cognee-test` and verify quality metrics
- [ ] T056 Update `quickstart.md` with any discovered edge cases or troubleshooting tips
- [ ] T057 Validate all Makefile targets work end-to-end

**Final Checkpoint**: All user stories complete, tests pass, documentation current

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1+US2 (Phase 3)**: Depends on Foundational - P0, MVP
- **US3 (Phase 4)**: Depends on Foundational - can run parallel to US1+US2
- **US4 (Phase 5)**: Depends on US1+US2 (needs init/sync working)
- **US5 (Phase 6)**: Depends on US1+US2 (needs search working)
- **US7 (Phase 7)**: Depends on US1+US2 (needs basic operations working)
- **US6 (Phase 8)**: Depends on US1+US2 (needs search working) - P2, lower priority
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational)
    │
    ├──────────────────────────────────────────┐
    ▼                                          ▼
Phase 3 (US1+US2) ─────────────────────► Phase 4 (US3)
    │                                          │
    ├──────────────┬──────────────┬────────────┤
    ▼              ▼              ▼            │
Phase 5 (US4)  Phase 6 (US5)  Phase 7 (US7)   │
    │              │              │            │
    ├──────────────┴──────────────┴────────────┘
    ▼
Phase 8 (US6)
    │
    ▼
Phase 9 (Polish)
```

### Within Each User Story

- Tests FIRST (if included) - ensure they FAIL before implementation
- Models/utilities before commands
- CLI commands last
- Makefile targets with CLI commands

### Parallel Opportunities

- T003, T004, T005 can run in parallel (different files)
- T006, T007 can run in parallel (different files)
- T010, T011 can run in parallel (different test files)
- T019, T033, T034 can run in parallel (unit tests)
- US3 (Phase 4) can run in parallel with US4, US5, US7 after Phase 3 complete

---

## Implementation Strategy

### MVP First (P0 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1+US2 (Cognee Cloud + Architecture Indexing)
4. **STOP and VALIDATE**: Run `make cognee-health` and `make cognee-search`
5. Deploy/demo if ready - basic memory working

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1+US2 → Test → **MVP!** (searchable architecture knowledge)
3. Add US3 → Test → Code intelligence added
4. Add US4 → Test → Automatic sync working
5. Add US5 → Test → MCP integration for Claude Code
6. Add US7 → Test → Operational tools complete
7. Add US6 → Test → Session recovery (nice to have)
8. Polish → Full quality validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All async operations use `asyncio.run()` in CLI
- All API keys via SecretStr, never hardcoded
