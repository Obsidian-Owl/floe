# floe Development Guide

**For**: Claude Code and AI developers
**Purpose**: Guide development toward target state architecture
**Philosophy**: Build the future, not maintain the past

---

## Epic Auto-Mode Recovery (CRITICAL - Read After Every Compaction)

**THIS SECTION IS CRITICAL**: After context compaction, skill instructions are lost but this file survives. Check for active workflows immediately.

### Check for Active Epic Auto-Mode

```bash
# Check if epic auto-mode was active before compaction
if [ -f ".agent/epic-auto-mode" ]; then
    cat .agent/epic-auto-mode  # Contains epic context
fi
```

**If `.agent/epic-auto-mode` exists, YOU MUST:**

1. **Read the state file** to understand current context:
   ```bash
   cat .agent/epic-auto-mode
   ```

2. **Continue implementing automatically** - do NOT wait for user prompt

3. **Follow the epic auto-mode workflow**:
   - Sync from Linear to get current task status
   - Find next ready task (status: backlog/unstarted)
   - Implement the task (TDD, SOLID, atomic commits)
   - Update Linear status to Done
   - Create Linear comment with completion summary
   - Commit changes
   - **Loop to next task immediately** (no confirmation)

4. **Only stop for**:
   - Design questions requiring user validation → Use `AskUserQuestion` tool
   - All tasks completed → Output "EPIC COMPLETE" banner, remove state file
   - Task blocked by dependency → Output "EPIC BLOCKED" banner, keep state file

### State File Format

The `.agent/epic-auto-mode` file contains JSON with recovery context:
```json
{
  "mode": "epic-auto",
  "feature_dir": "specs/epic-name",
  "epic_name": "epic-name",
  "started_at": "2026-01-17T10:30:00Z",
  "last_task": "T005",
  "last_linear_id": "FLO-123",
  "total_tasks": 15,
  "completed_before_compact": 4
}
```

### Recovery Procedure

After compaction with active epic-auto-mode:

1. Read `.agent/epic-auto-mode` for context
2. Read `{feature_dir}/.linear-mapping.json` for task mappings
3. Query Linear for current status of all tasks
4. Find next task with status `backlog` or `unstarted`
5. **Resume implementation immediately** - you are in auto-mode

**DO NOT** ask the user "should I continue?" - the existence of the state file IS the user's instruction to continue.

### Cancellation

**To cancel epic auto-mode**, the user can:
1. **Remove the state file manually**: `rm .agent/epic-auto-mode`
2. **Send a cancel message**: Type "cancel" or "stop" during implementation
3. **Use Ctrl+C**: Interrupt Claude Code execution

If cancelled mid-epic, Claude should acknowledge and NOT resume unless explicitly asked.

### Completion Cleanup

**CRITICAL**: When epic completes successfully, remove the state file **IMMEDIATELY BEFORE** any other output:

```bash
rm -f .agent/epic-auto-mode  # FIRST - prevents confusion on compaction
```

Then output the completion banner. This order prevents edge cases where compaction occurs between banner and cleanup.

---

## Vision

**floe** is an open platform (Apache 2.0) for building internal data platforms.

Choose your stack from 11 plugin types. Define your standards once. Data teams get opinionated workflows with governance built-in.

**Start with a single platform. Scale to Data Mesh.**

---

## Quick Reference

### Essential Commands

```bash
# Testing (K8s-native)
make test              # All tests in K8s (Kind cluster)
make test-unit         # Unit tests only (fast, no K8s)

# Quality
make check             # Full CI checks (lint, type, security, test)
make lint              # Ruff linting + formatting
make typecheck         # mypy --strict

# Pre-PR Review
/speckit.test-review   # Validate test quality before PR

# Deployment
make deploy-local      # Deploy platform services to Kind
make demo-e2e          # End-to-end validation
```

### Where to Find Things

| Topic | Location |
|-------|----------|
| **Architecture** | `docs/architecture/` - Four-layer model, plugin system, OCI registry |
| **Testing Strategy** | `TESTING.md` - K8s-native testing, test organization |
| **Workflow Integration** | `docs/guides/linear-workflow.md` - SpecKit + Beads + Linear |
| **ADRs** | `docs/architecture/adr/` - Architectural decisions |

---

## Target State Architecture

> **Reference**: `docs/architecture/` contains authoritative design. Use progressive disclosure - read details when needed.

### Four-Layer Model

```
Layer 1: FOUNDATION     → PyPI packages, plugin interfaces
Layer 2: CONFIGURATION  → OCI registry artifacts (manifest.yaml)
Layer 3: SERVICES       → K8s Deployments (Dagster, Polaris, Cube)
Layer 4: DATA           → K8s Jobs (dbt run, dlt ingestion)
```

**Key Principle**: Configuration flows DOWNWARD ONLY (1→2→3→4).

**FORBIDDEN**: Layer 4 modifying Layer 2 configuration.

### Two-File Configuration

| File | Owner | Changes |
|------|-------|---------|
| `manifest.yaml` | Platform Team | Rarely (governance, plugin selection) |
| `floe.yaml` | Data Engineers | Frequently (pipelines, schedules) |

### Plugin Architecture

**ENFORCED** (non-negotiable):
- Apache Iceberg (storage format)
- dbt (transformation framework) - SQL compilation via dbt ENFORCED; execution environment PLUGGABLE (DBTPlugin)
- OpenTelemetry (observability)
- OpenLineage (lineage)
- Kubernetes-native (deployment)

**PLUGGABLE** (platform team selects):
- Compute: DuckDB, Snowflake, Databricks, Spark, BigQuery
- Orchestrator: Dagster, Airflow 3.x
- Catalog: Polaris, AWS Glue, Hive
- Semantic Layer: Cube, dbt Semantic Layer
- Ingestion: dlt, Airbyte

**See**: `docs/architecture/opinionation-boundaries.md` for complete list.

---

## Development Workflow

### SpecKit + Beads + Linear Integration

**Source of Truth**: Linear (issue tracking)
**Local Cache**: Beads (offline work)
**Planning**: SpecKit (feature breakdown)

```bash
# 1. Sync from Linear
bd linear sync --pull

# 2. See available work
/speckit.implement

# 3. Auto-implement next ready task
/speckit.implement  # Claims task, updates Linear, commits

# 4. Pre-PR validation
/speckit.test-review   # Test quality
/speckit.wiring-check  # Is new code wired into system?
/speckit.merge-check   # Contract stability, merge readiness

# 5. Create PR
/speckit.pr  # Links Linear issues, generates summary
```

**Complete Workflow**: See `docs/guides/linear-workflow.md`

### Development Cycle (with Integration Thinking)

Integration is planned upfront (Phase 1), not discovered later. Each phase has integration checkpoints.

```
Phase 1: Planning (Integration Thinking Starts Here)
├── /speckit.specify     → Create spec.md
│   └── Document: entry points, dependencies, outputs
├── /speckit.clarify     → Resolve ambiguities (incl. integration)
├── /speckit.plan        → Generate plan.md
│   └── Document: integration design, cleanup required
├── /speckit.tasks       → Create tasks.md
└── /speckit.taskstolinear → Sync to Linear

Phase 2: Implementation (Per-Task Integration Checks)
├── bd linear sync --pull → Get task status
├── /speckit.implement    → Implement task
│   ├── Step 7: Check integration (new code reachable)
│   └── Cleanup: Remove replaced code, orphaned tests
└── Repeat until all tasks complete

Phase 3: Pre-PR Validation
├── /speckit.test-review   → Test quality
├── /speckit.wiring-check  → Is new code wired into system?
├── /speckit.merge-check   → Safe to merge? (contracts, conflicts)
└── /speckit.pr            → Create PR

Phase 4: Merge
└── Merge when CI passes
```

**Key shift**: Integration is planned upfront, not an afterthought. Cleanup is expected, not optional.

---

## Code Navigation & Understanding (LSP-First)

**CRITICAL**: Always understand existing code before making changes. Use LSP tools proactively.

### Navigation Workflow

```bash
# 1. Find files by pattern
Glob("packages/*/tests/unit/test_*.py")

# 2. Search for specific code
Grep("class ComputePlugin", pattern="class ComputePlugin")

# 3. Read before editing
Read("packages/floe-core/src/floe_core/schemas.py")

# 4. Then make changes
Edit(...)
```

### Best Practices (LSP-First)

**Priority 1: LSP for Precise Navigation**

| Scenario | LSP Feature | Why |
|----------|-------------|-----|
| Find where something is defined | Go to Definition | Jump directly to source |
| Find all usages of a symbol | Find References | See every usage across codebase |
| Get documentation and type info | Hover | See docstrings, types, examples inline |
| List all symbols in a file | Document Symbols | Fast file navigation |

**Priority 2: Text-Based Tools (When LSP Unavailable)**

| Scenario | Tool | When to Use |
|----------|------|-------------|
| Pattern matching across files | `Grep` | Regex searches, multi-file patterns |
| File discovery by name/path | `Glob` | Finding files matching patterns |
| Understanding full file context | `Read` | **MANDATORY before Edit** |
| Complex codebase exploration | `Task(Explore)` | Multi-step discovery workflows |

**NEVER**:
- ❌ Edit files you haven't read (Edit tool requires prior Read)
- ❌ Use `Bash(cat)` when `Read` tool exists
- ❌ Use `Bash(find)` when `Glob` tool exists
- ❌ Use `Bash(grep)` when `Grep` tool exists
- ❌ Guess at code structure without LSP/search

**ALWAYS**:
- ✅ Use LSP "Go to Definition" before Grep for finding definitions
- ✅ Use LSP "Find References" before Grep for finding usages
- ✅ Use LSP "Hover" to read documentation inline
- ✅ Read files before editing (understand context first)
- ✅ Delegate complex exploration to `Task(Explore)` agent

**Note on Finding Implementations**: Pyright doesn't support "Find Implementations". Use **Find References** on the base class/Protocol to see all usages, or use **Grep**: `Grep("class.*\(ProfileGenerator\)", type="py")`

**Example Workflow**:
```python
# 1. Find where ComputePlugin is defined (LSP Go to Definition)
# → Navigate to packages/floe-core/src/floe_core/plugin_interfaces.py

# 2. Hover over ComputePlugin (LSP Hover)
# → See full docstring, attributes, example usage

# 3. Find all usages of ComputePlugin (LSP Find References)
# → See where it's imported and subclassed across the codebase

# 4. Read implementation before modifying
Read("plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py")
# Review: Understand existing implementation, dependencies, patterns

# 5. Make informed changes
Edit("plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py",
     old_string="...", new_string="...")
```

### Writing Effective Docstrings

**Why This Matters for LSP**: Good docstrings directly improve LSP features (Hover, autocomplete, IntelliSense). When you hover over a function, LSP shows the docstring—make it count.

**Standard**: Google-style docstrings (consistent across the codebase)

```python
def generate_profiles(
    artifacts: CompiledArtifacts,
    environment: str = "dev"
) -> dict[str, Any]:
    """Generate dbt profiles.yml from compiled artifacts.

    Resolves credentials at runtime from environment variables or K8s secrets.
    Supports multiple compute targets (DuckDB, Snowflake, BigQuery, etc.).

    Args:
        artifacts: Compiled artifacts containing resolved platform configuration.
        environment: Target environment (dev, staging, prod). Defaults to "dev".

    Returns:
        Dictionary containing dbt profiles.yml structure with resolved credentials.

    Raises:
        CredentialError: If required credentials are missing or invalid.
        ValidationError: If artifacts schema validation fails.

    Examples:
        >>> artifacts = CompiledArtifacts.from_json_file("compiled.json")
        >>> profiles = generate_profiles(artifacts, environment="production")
        >>> profiles["floe"]["target"]
        'production'
    """
    pass
```

**What Makes a Good Docstring**:
- **Summary line**: One-line description (what, not how)
- **Detailed description**: When needed, explain why and context
- **Args**: Every parameter, with type info if not in type hints
- **Returns**: What the function returns and its meaning
- **Raises**: All exceptions that can be raised
- **Examples**: Doctest-style examples showing typical usage

**Bad vs Good**:

```python
# ❌ BAD - No value to LSP users
def process(data):
    """Process data."""
    pass

# ✅ GOOD - LSP Hover shows useful information
def process(data: dict[str, Any]) -> ProcessedData:
    """Transform raw data into validated ProcessedData model.

    Applies validation rules, normalizes field names, and converts
    types according to the schema. Invalid records are logged and skipped.

    Args:
        data: Raw data dictionary from external source.

    Returns:
        ProcessedData instance with validated and normalized fields.

    Raises:
        ValidationError: If required fields are missing.
    """
    pass
```

**See**: `.claude/rules/python-standards.md` for complete docstring examples and standards

---

## Core Principles

### 1. Technology Ownership (NON-NEGOTIABLE)

Each technology owns its domain exclusively:

| Technology | Owns | Python Code MUST NOT |
|------------|------|---------------------|
| **dbt** | ALL SQL compilation, dialect translation | Parse, validate, or transform SQL |
| **Dagster** | Orchestration, assets, schedules | Execute SQL, manage Iceberg tables |
| **Iceberg** | Storage format, ACID, time travel | Define orchestration, execute SQL |
| **Polaris** | Catalog management (REST API) | Write to storage directly |
| **Cube** | Semantic layer, consumption APIs | Execute SQL directly, orchestrate |

**Plugin Delegation**: SemanticLayerPlugin → ComputePlugin for database connection.

**See**: `.claude/rules/component-ownership.md`

### 2. Contract-Driven Integration

**CompiledArtifacts** is the SOLE contract between packages:

```python
# ✅ CORRECT - floe-core compiles
artifacts = compile_data_product(product_yaml, platform_manifest)
artifacts.to_json_file("target/compiled_artifacts.json")

# ✅ CORRECT - floe-dagster loads
artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")
assets = create_assets_from_artifacts(artifacts)

# ❌ FORBIDDEN - direct FloeSpec passing
def create_assets(spec: FloeSpec):  # NO! Use CompiledArtifacts
    ...
```

**Contract Versioning**:
- MAJOR: Breaking changes (remove field, change type)
- MINOR: Additive changes (add optional field)
- PATCH: Documentation, internal refactoring

**See**: `.claude/rules/pydantic-contracts.md`

### 3. Plugin Development Standards

**All plugins MUST**:
- Register via entry points (`floe.orchestrators`, `floe.computes`, etc.)
- Inherit from appropriate ABC (ComputePlugin, OrchestratorPlugin, etc.)
- Declare `PluginMetadata` (name, version, floe_api_version)
- Use Pydantic models for configuration (NO hardcoded values)
- Use `SecretReference` for credentials (NEVER hardcoded secrets)
- Have >80% test coverage (discovery, compliance, functional)

**See**: `docs/architecture/plugin-system/index.md`

### 4. Testing Standards

**K8s-Native ONLY**:
- All tests run in Kubernetes (Kind cluster locally)
- Integration tests use real services (Polaris, S3, PostgreSQL)
- No Docker Compose (deprecated in target state)

**Test Organization**:
- `packages/*/tests/unit/` - Package-specific, fast, mocked
- `packages/*/tests/integration/` - Real services, K8s
- `tests/contract/` - Cross-package contracts (ROOT level)

**Pre-PR Review**:
```bash
/speckit.test-review  # Validates quality, traceability, security
```

**See**: `TESTING.md` for complete testing guide

### 5. Security First

**NEVER**:
- Use `eval()`, `exec()`, `pickle.loads()` on untrusted data
- Use `subprocess.run(..., shell=True)`
- Hardcode secrets (use `SecretStr` + environment variables)
- Log secrets or PII

**See**: `.claude/rules/security.md`

---

## Target State Package Structure

```
floe/
├── floe-core/           # Schemas, interfaces, enforcement engine
├── floe-cli/            # CLI for Platform Team and Data Team
├── floe-dbt/            # ENFORCED: dbt integration
├── floe-iceberg/        # ENFORCED: Iceberg utilities
│
├── plugins/             # ALL PLUGGABLE COMPONENTS (Epic 5)
│   ├── floe-compute-duckdb/
│   │   ├── src/floe_compute_duckdb/
│   │   └── tests/       # Package-specific tests ONLY
│   │       ├── conftest.py  # NO __init__.py (namespace collision)
│   │       ├── unit/        # Fast, mocked, host execution
│   │       ├── integration/ # Real services, K8s execution
│   │       └── e2e/         # Package-specific workflows (rare)
│   ├── floe-orchestrator-dagster/
│   ├── floe-catalog-polaris/
│   └── ...
│
├── tests/               # Cross-package tests ONLY (ROOT LEVEL)
│   ├── conftest.py
│   ├── contract/        # MANDATORY: CompiledArtifacts, plugin ABCs
│   │   ├── test_compiled_artifacts_schema.py
│   │   ├── test_core_to_dagster_contract.py
│   │   └── test_core_to_dbt_contract.py
│   └── e2e/             # OPTIONAL: Full platform workflows
│       └── test_demo_flow.py
│
├── charts/
│   ├── floe-platform/   # Meta-chart for platform services
│   └── floe-jobs/       # Base chart for pipeline jobs
│
├── demo/                # Demo data engineering project
├── testing/
│   ├── base_classes/    # IntegrationTestBase, BaseProfileGeneratorTests
│   ├── fixtures/        # Shared test fixtures
│   ├── k8s/             # Kind configuration, Helm values
│   └── traceability/    # Test quality analysis (/speckit.test-review)
└── docs/
```

### Test Organization Rules (CRITICAL)

**Decision Tree**: Where should my test go?

| Question | Answer → Location |
|----------|-------------------|
| Imports from MULTIPLE packages? | **YES** → `tests/contract/` or `tests/e2e/` |
| Validates cross-package contract? | **YES** → `tests/contract/test_X_to_Y_contract.py` |
| Full platform workflow? | **YES** → `tests/e2e/test_X_flow.py` |
| Single package only? | **YES** → `plugins/floe-X/tests/{tier}/test_*.py` |

**Test Tier Selection**:

| Tier | Location | Needs Services? | Execution |
|------|----------|----------------|-----------|
| **Unit** | `tests/unit/` | No (mocks only) | Host (fast) |
| **Contract** | `tests/contract/` (ROOT) | No (schema only) | Host (fast) |
| **Integration** | `tests/integration/` | Yes (Polaris, S3, DB) | K8s (Kind) |
| **E2E** | `tests/e2e/` | Yes (full stack) | K8s (Kind) |

**Examples**:
- ✅ `floe-core/tests/unit/test_compiler.py` - Tests ONLY floe-core
- ✅ `tests/contract/test_core_to_dagster_contract.py` - Tests floe-core + floe-dagster
- ❌ `tests/integration/test_polaris_catalog.py` - Should be `plugins/floe-catalog-polaris/tests/integration/`

**See**: `.claude/rules/test-organization.md` for complete decision tree and anti-patterns

---

## Target State Architecture

**Philosophy**: Build the future. Quality over speed. Nuclear changes acceptable.

**Principle**: Build toward target state architecture documented in `docs/`, never compromise on quality.

---

## Code Quality Standards

**Pre-commit checklist**:
- Type hints on ALL functions (`mypy --strict` passes)
- Pydantic v2 syntax (`@field_validator`, `model_config`)
- Ruff linting passes
- No dangerous constructs (`eval`, `exec`, `shell=True`)
- No secrets in code (environment variables only)
- Tests pass with >80% coverage
- Layer boundary verification (no cross-layer violations)

**Automated Enforcement**:
- Pre-commit hooks (formatting, linting)
- CI pipeline (type checking, security scans, tests)
- SonarQube quality gates

**See**: `.claude/rules/python-standards.md`, `.claude/rules/sonarqube-quality.md`

---

## Context Management

### Subagent Delegation (MANDATORY)

**ALWAYS delegate to preserve main context**:

| Task | Delegate To | Why |
|------|-------------|-----|
| Docker/container logs | `docker-log-analyser` | Extracts errors only |
| K8s pod debugging | `helm-debugger` | Targeted extraction |
| Helm chart issues | `helm-debugger` | Validates charts first |
| dbt work | `dbt-skill` | Domain expertise |
| Pydantic models | `pydantic-skill` | Contract patterns |

**See**: `.claude/rules/agent-delegation.md`, `.claude/rules/context-management.md`

### Progressive Disclosure

**Don't dump everything into context**:
- ✅ Point to detailed docs (`docs/architecture/plugin-system/index.md`)
- ✅ Read specific sections when needed
- ❌ Copy entire architecture docs into conversation

---

## Memory Workflow

The **agent-memory** system provides persistent context across sessions via a Cognee Cloud knowledge graph.

### Quick Reference

```bash
# Search for prior decisions/context
./scripts/memory-search "plugin architecture"

# Save decisions for future sessions
./scripts/memory-save --decisions "Chose Pydantic v2 for validation" --issues "FLO-123"

# Add content to knowledge graph
./scripts/memory-add "Important: Use camelCase for Cognee API fields"
./scripts/memory-add --file docs/architecture/new-pattern.md
```

### When to Use

| Action | Command | When |
|--------|---------|------|
| **Search** | `./scripts/memory-search` | Before making architecture decisions |
| **Save** | `./scripts/memory-save` | After making significant decisions |
| **Add** | `./scripts/memory-add` | When creating reusable knowledge |

### Automatic Integration

- **Session Start**: Hook automatically queries for prior context (see startup logs)
- **SpecKit Skills**: `/speckit.plan` and `/speckit.specify` search memory before decisions
- **Epic Recovery**: SessionStart hook detects `.agent/epic-auto-mode` after compaction

### If Agent-Memory Unavailable

All memory operations are **non-blocking**. If `COGNEE_API_KEY` or `OPENAI_API_KEY` are not set:
- Scripts exit gracefully (exit code 0)
- Workflow continues without memory integration
- Decisions are still captured in plan artifacts and Linear comments

**See**: `devtools/agent-memory/` for full documentation

---

## Getting Help

```bash
# Documentation
/help                           # Claude Code help
make help                       # Makefile targets

# Testing
/speckit.test-review            # Pre-PR test quality review
make test                       # Run all tests (K8s)

# Debugging
bd stats                        # Beads issue statistics
bd ready                        # See available work
Linear app                      # Team progress view
```

**Issue Reporting**: https://github.com/anthropics/claude-code/issues (for Claude Code feedback)

---

## Key References

- **Architecture**: `docs/architecture/ARCHITECTURE-SUMMARY.md`
- **Testing**: `TESTING.md`
- **Linear Workflow**: `docs/guides/linear-workflow.md`
- **Constitution**: `.specify/memory/constitution.md` (8 core principles)

---

**Remember**: Build toward the target state architecture documented in `docs/`. Quality over speed. Nuclear changes acceptable.

## Active Technologies
- Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + Pydantic v2 (config validation), structlog (logging) (001-plugin-registry)
- N/A (in-memory registry, plugins are entry points in installed packages) (001-plugin-registry)
- Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + PyIceberg >=0.5.0, Pydantic v2, structlog, opentelemetry-api, httpx (for OAuth2) (001-catalog-plugin)
- N/A (catalog manages metadata; storage is handled by StoragePlugin) (001-catalog-plugin)
- Python 3.10+ (required for floe-core compatibility) + opentelemetry-api>=1.20.0, opentelemetry-sdk>=1.20.0, opentelemetry-exporter-otlp>=1.20.0, structlog (001-opentelemetry)
- N/A (telemetry flows to OTLP Collector, not stored locally) (001-opentelemetry)
- Python 3.10+ (required for improved importlib.metadata.entry_points API) + Pydantic v2 (BaseModel, Field, ConfigDict, field_validator), PyYAML, structlog (001-manifest-schema)
- N/A (schema definitions only; OCI registry loading deferred to Epic 2B) (001-manifest-schema)
- Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + Pydantic v2 (config validation), structlog (logging), duckdb>=0.9.0 (reference implementation) (001-compute-plugin)
- N/A (plugin system is stateless; dbt profiles.yml is file-based output) (001-compute-plugin)
- Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + Pydantic v2, PyYAML, structlog, argparse (stdlib) (2b-compilation-pipeline)
- File-based (JSON/YAML artifacts in `target/` directory) (2b-compilation-pipeline)
- Python 3.10+ (Cognee requirement, matches floe standard) (10a-agent-memory)
- Cognee Cloud (SaaS) - managed vector + graph storage, no self-hosted backends (10a-agent-memory)
- Python 3.10+ (required for floe-core compatibility) + httpx (HTTP client), pytest (testing), structlog (logging), pydantic (validation) (10b-agent-memory-quality)
- Cognee Cloud (SaaS) - REST API integration, no local storage (10b-agent-memory-quality)
- Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + PyIceberg >=0.5.0, Pydantic v2, structlog, opentelemetry-api >=1.20.0, pyarrow (4d-storage-plugin)
- Iceberg tables via PyIceberg (S3/GCS/Azure via StoragePlugin FileIO) (4d-storage-plugin)
- Python 3.11 (7a-identity-secrets)
- N/A (plugins access external secrets/identity backends) (7a-identity-secrets)
- Python 3.10+ (matches floe-core requirements) + Pydantic v2 (schemas), structlog (logging), opentelemetry-api (tracing) (3a-policy-enforcer)
- N/A (PolicyEnforcer is stateless; reads dbt manifest.json) (3a-policy-enforcer)
- Python 3.11 + kubernetes>=27.0.0, pydantic>=2.0.0, pyyaml>=6.0, structlog (7b-k8s-rbac)
- File-based (YAML manifests in `target/rbac/` directory) (7b-k8s-rbac)
- Python 3.10+ (matches floe-core requirements) + Click>=8.1.0 (CLI framework), Rich (optional, enhanced output), Pydantic>=2.0 (config validation), structlog (logging) (11-cli-unification)
- N/A (CLI is stateless; outputs to filesystem) (11-cli-unification)
- Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + Pydantic v2, structlog, pytest, concurrent.futures (ThreadPoolExecutor), PyIceberg (12a-tech-debt-q1-2026)
- N/A (refactoring existing code, no new storage) (12a-tech-debt-q1-2026)
- Python 3.10+ (matches floe-core requirements) + Pydantic v2 (schemas), structlog (logging), PyYAML, kubernetes client (validation) (7c-network-pod-security)
- File-based (YAML manifests in `target/network/` directory) (7c-network-pod-security)

## Cognee Cloud API Quirks (CRITICAL)

**IMPORTANT**: The Cognee Cloud REST API uses **camelCase** field names, NOT snake_case.

### Field Name Requirements

| Endpoint | Wrong (snake_case) | Correct (camelCase) |
|----------|-------------------|---------------------|
| `/api/add` | `data`, `dataset_name` | `textData`, `datasetName` |
| `/api/search` | `search_type`, `top_k` | `searchType`, `topK` |
| `/api/cognify` | `datasets` | `datasets` (already correct) |

**Bug History**: Using `"data"` instead of `"textData"` causes the API to use its default value
`["Warning: long-term memory may contain dad jokes!"]` for ALL content. This bug was discovered
2026-01-16 after all synced content was replaced with this default.

### Response Format Variations

The Cognee API returns different formats - implementation must handle all:
```python
# Format 1: Direct list
[{"content": "...", "score": 0.9}, ...]

# Format 2: Dict with results
{"results": [{"content": "...", "score": 0.9}, ...]}

# Format 3: Dict with data
{"data": [{"content": "...", "score": 0.9}, ...]}

# Format 4: Nested search_result
[{"search_result": ["text1", "text2"], "dataset_id": "..."}, ...]
```

### Contract Tests Required

All Cognee API integrations MUST have contract tests that validate field names. See:
- `devtools/agent-memory/tests/contract/test_cognee_api_contract.py`
- Epic 10B for validation requirements

### Memify: SDK-Only (FR-006, FR-007)

The `memify` command uses the **Cognee Cloud SDK** (`cogwit`), NOT the REST API.

**Why SDK instead of REST:**
- Memify is NOT available via the Cognee Cloud REST API
- The SDK handles incremental graph optimization server-side
- Error responses from SDK differ from REST API errors

**SDK Integration Pattern:**
```python
from cognee.modules.cognee_cloud import cogwit, CogwitConfig

sdk_config = CogwitConfig(api_key=api_key)
sdk = cogwit(sdk_config)
result = await sdk.memify(dataset_name="my_dataset")
```

**Error Handling:** SDK errors require separate handling from REST API errors.
See `CogneeClient.memify()` in `devtools/agent-memory/src/agent_memory/cognee_client.py`.

## Recent Changes
- 7c-network-pod-security: Added Python 3.10+ (matches floe-core requirements) + Pydantic v2 (schemas), structlog (logging), PyYAML, kubernetes client (validation)
- 12a-tech-debt-q1-2026: Added Python 3.10+ (required for `importlib.metadata.entry_points()` improved API) + Pydantic v2, structlog, pytest, concurrent.futures (ThreadPoolExecutor), PyIceberg
- 11-cli-unification: Added Python 3.10+ (matches floe-core requirements) + Click>=8.1.0 (CLI framework), Rich (optional, enhanced output), Pydantic>=2.0 (config validation), structlog (logging)
