# Implementation Plan: CLI Unification

**Branch**: `11-cli-unification` | **Date**: 2026-01-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/11-cli-unification/spec.md`

## Summary

Unify the conflicting CLI implementations in floe-cli (Click) and floe-core (argparse) into a single Click-based CLI in floe-core. This resolves the entry point conflict where both packages register `floe` as an entry point, and enables Epic 3B completion by providing CLI access to enforcement report export.

**Technical Approach**: Migrate floe-core CLI from argparse to Click, move RBAC commands from floe-cli, add enforcement export flags, and deprecate floe-cli package.

## Technical Context

**Language/Version**: Python 3.10+ (matches floe-core requirements)
**Primary Dependencies**: Click>=8.1.0 (CLI framework), Rich (optional, enhanced output), Pydantic>=2.0 (config validation), structlog (logging)
**Storage**: N/A (CLI is stateless; outputs to filesystem)
**Testing**: pytest with Click's CliRunner, golden file snapshots for regression testing
**Target Platform**: Linux/macOS/Windows (cross-platform CLI)
**Project Type**: Single project (floe-core package modification)
**Performance Goals**: `floe --help` <1s, `floe platform compile` <5s for 500+ models
**Constraints**: Backward compatibility for RBAC command output, no breaking changes to existing RBAC workflows
**Scale/Scope**: ~30 CLI commands across 4 groups (platform, rbac, artifact, data team stubs)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core owns CLI)
- [x] No SQL parsing/validation in Python (CLI invokes existing modules)
- [x] No orchestration logic outside floe-dagster (CLI triggers compile, not orchestration)

**Principle II: Plugin-First Architecture**
- [N/A] New configurable component uses plugin interface (CLI is not a plugin)
- [N/A] Plugin registered via entry point (CLI entry point, not plugin)
- [N/A] PluginMetadata declares name, version, floe_api_version (not applicable)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (CLI doesn't change Iceberg/OTel/etc.)
- [x] Pluggable choices documented in manifest.yaml (CLI reads, doesn't modify)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (CLI invokes compiler, outputs artifacts)
- [x] Pydantic v2 models for all schemas (existing enforcement models)
- [x] Contract changes follow versioning rules (no contract changes in this epic)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (RBAC audit/diff require K8s)
- [x] No `pytest.skip()` usage (tests fail if infrastructure missing)
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (file paths validated)
- [x] Credentials use SecretStr (registry auth via env vars)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (CLI invokes Layer 2 compile)
- [x] Layer ownership respected (Platform Team CLI for governance)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (compile already traces)
- [N/A] OpenLineage events for data transformations (CLI doesn't transform data)

## Project Structure

### Documentation (this feature)

```text
specs/11-cli-unification/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research findings
├── data-model.md        # CLI command structure model
├── quickstart.md        # Developer quickstart
├── contracts/           # CLI interface contracts
│   └── cli-commands.md  # Command interface specification
├── checklists/          # Validation checklists
│   └── requirements.md  # Requirements checklist
└── tasks.md             # Task breakdown (Phase 2)
```

### Source Code (repository root)

```text
packages/floe-core/
├── pyproject.toml                     # Add click dependency
└── src/floe_core/cli/
    ├── __init__.py                    # Export main()
    ├── main.py                        # REWRITE: Click root group
    ├── platform/                      # NEW: Platform team commands
    │   ├── __init__.py
    │   ├── compile.py                 # floe platform compile (with enforcement)
    │   ├── test.py                    # floe platform test (stub)
    │   ├── publish.py                 # floe platform publish (stub)
    │   ├── deploy.py                  # floe platform deploy (stub)
    │   └── status.py                  # floe platform status (stub)
    ├── rbac/                          # MIGRATE from floe-cli
    │   ├── __init__.py
    │   ├── generate.py                # floe rbac generate
    │   ├── validate.py                # floe rbac validate
    │   ├── audit.py                   # floe rbac audit
    │   └── diff.py                    # floe rbac diff
    ├── artifact/                      # MIGRATE from existing
    │   ├── __init__.py
    │   └── push.py                    # floe artifact push
    └── data/                          # NEW: Data team stubs
        ├── __init__.py
        ├── compile.py                 # floe compile (stub)
        ├── validate.py                # floe validate (stub)
        ├── run.py                     # floe run (stub)
        └── test.py                    # floe test (stub)

packages/floe-core/tests/
├── unit/cli/                          # Unit tests for CLI
│   ├── test_main.py
│   ├── test_platform_compile.py
│   └── test_rbac_commands.py
└── integration/cli/                   # Integration tests
    ├── test_rbac_integration.py       # RBAC with real K8s
    └── test_compile_integration.py    # Compile with real files

tests/contract/                        # ROOT: Cross-package contracts
└── test_cli_output_contracts.py       # Golden file regression tests

packages/floe-cli/                     # DEPRECATED after migration
└── [archived]
```

**Structure Decision**: Single package modification (floe-core) with CLI code in `src/floe_core/cli/`. RBAC commands migrate from floe-cli to floe-core. floe-cli package deprecated after migration complete.

## Implementation Phases

### Phase 1: CLI Framework Migration

**Goal**: Replace argparse with Click in floe-core

**Tasks**:
1. Add Click dependency to floe-core/pyproject.toml
2. Create Click root group in main.py
3. Add `--version` flag
4. Add error handling with stderr output
5. Wire up basic help formatting

**Files Modified**:
- `packages/floe-core/pyproject.toml`
- `packages/floe-core/src/floe_core/cli/main.py`
- `packages/floe-core/src/floe_core/cli/__init__.py`

### Phase 2: Platform Commands

**Goal**: Implement `floe platform *` command group

**Tasks**:
1. Create platform/ directory structure
2. Implement `floe platform compile` with all options
3. Add enforcement export flags (`--enforcement-report`, `--enforcement-format`)
4. Implement stub commands (test, publish, deploy, status)
5. Unit tests for compile command

**Files Created**:
- `packages/floe-core/src/floe_core/cli/platform/__init__.py`
- `packages/floe-core/src/floe_core/cli/platform/compile.py`
- `packages/floe-core/src/floe_core/cli/platform/test.py`
- `packages/floe-core/src/floe_core/cli/platform/publish.py`
- `packages/floe-core/src/floe_core/cli/platform/deploy.py`
- `packages/floe-core/src/floe_core/cli/platform/status.py`

### Phase 3: RBAC Migration

**Goal**: Migrate RBAC commands from floe-cli to floe-core

**Tasks**:
1. Capture baseline output snapshots (golden files)
2. Create rbac/ directory structure
3. Migrate generate command
4. Migrate validate command
5. Migrate audit command
6. Migrate diff command
7. Verify output equivalence against golden files

**Files Migrated**:
- `packages/floe-cli/src/floe_cli/commands/rbac.py` → `packages/floe-core/src/floe_core/cli/rbac/`

### Phase 4: Artifact Commands

**Goal**: Migrate artifact push to Click

**Tasks**:
1. Create artifact/ directory structure
2. Convert artifact push from argparse to Click
3. Preserve existing functionality
4. Unit tests

**Files Modified/Created**:
- `packages/floe-core/src/floe_core/cli/artifact/__init__.py`
- `packages/floe-core/src/floe_core/cli/artifact/push.py`

### Phase 5: Data Team Stubs

**Goal**: Create stub commands for Data Team CLI

**Tasks**:
1. Create data/ directory structure
2. Implement compile stub
3. Implement validate stub
4. Implement run stub
5. Implement test stub

**Files Created**:
- `packages/floe-core/src/floe_core/cli/data/__init__.py`
- `packages/floe-core/src/floe_core/cli/data/compile.py`
- `packages/floe-core/src/floe_core/cli/data/validate.py`
- `packages/floe-core/src/floe_core/cli/data/run.py`
- `packages/floe-core/src/floe_core/cli/data/test.py`

### Phase 6: Deprecation and Cleanup

**Goal**: Deprecate floe-cli package

**Tasks**:
1. Remove floe-cli from workspace dependencies
2. Update root pyproject.toml
3. Add deprecation notice to floe-cli
4. Update documentation
5. Run full regression test suite

**Files Modified**:
- `pyproject.toml` (root)
- `packages/floe-cli/README.md` (deprecation notice)

### Phase 7: Verification

**Goal**: Verify all success criteria

**Tasks**:
1. SC-001: Verify `floe --help` <1s
2. SC-002: Verify compile performance (500+ models <5s)
3. SC-003: Verify RBAC output equivalence (golden files)
4. SC-004: Verify no entry point conflicts
5. SC-005: Verify all CLI tests pass
6. SC-006: Verify help text readability
7. SC-007: Verify compile functionality preserved

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| RBAC output format changes | Medium | High | Golden file regression tests, capture baselines before migration |
| Click dependency conflicts | Low | Medium | Version pin Click>=8.1.0, test in clean virtualenv |
| Missing optional dependencies | Medium | Low | Graceful error messages with install instructions |
| Entry point order issues | Low | High | Remove floe-cli entry point, verify single entry point |

## Dependencies

- **ADR-0047**: CLI Architecture decision (accepted)
- **Epic 3B**: Policy Validation Enhancement (blocked by this epic, provides enforcement module)
- **Epic 7B**: K8s RBAC Plugin (provides RBAC generation logic to migrate)

## Complexity Tracking

No constitution violations requiring justification. This is a migration/refactoring epic with minimal architectural changes.
