# ADR-0047: CLI Architecture

## Status

Accepted

## Context

floe has two CLI packages with conflicting entry points:

| Package | Framework | Entry Point | Commands |
|---------|-----------|-------------|----------|
| `floe-cli` | Click | `floe = "floe_cli.main:cli"` | rbac/* |
| `floe-core` | argparse | `floe = "floe_core.cli:main"` | compile, artifact |

**Problem**: Both packages register the same `floe` entry point. Whichever package installs last wins, breaking the other's commands.

**Impact**:
- Epic 3B (Policy Validation) blocked - cannot add `--enforcement-report` flag to `floe platform compile`
- Inconsistent UX - different frameworks, different argument styles
- Maintenance burden - CLI logic split across packages

No formal ADR documented CLI framework selection or command organization.

## Decision

### 1. Framework: Click

**Rationale**:
- Already used in floe-cli (RBAC commands work well)
- Better nested command group support (critical for target architecture)
- Native type annotations via `click.option()`
- Richer UX (colors, progress bars, tables via `rich`)
- Consistent with dbt-core, Dagster CLI patterns

### 2. Location: Unified in floe-core

**Rationale**:
- Central location for schemas, validation, enforcement
- Single entry point maintenance
- Reduces cross-package dependencies
- All CLI logic co-located with business logic

### 3. Command Organization: Per ARCHITECTURE-SUMMARY.md

```
floe                           # Root command
├── platform/                  # Platform Team commands
│   ├── compile               # Build artifacts, run enforcement
│   ├── test                  # Policy tests
│   ├── publish               # Push to OCI registry
│   ├── deploy                # Deploy services to K8s
│   └── status                # Health check
├── rbac/                      # Platform RBAC management
│   ├── generate              # Generate RBAC manifests
│   ├── validate              # Validate RBAC configs
│   ├── audit                 # Audit current RBAC state
│   └── diff                  # Compare RBAC configurations
├── compile                    # Data Team: validate spec
├── validate                   # Data Team: validate floe.yaml
├── run                        # Data Team: execute pipeline
└── test                       # Data Team: dbt tests
```

**Two-Team UX Model**:
- **Platform Team**: `floe platform *` - governance, deployment, infrastructure
- **Data Team**: `floe compile`, `floe run`, `floe test` - day-to-day pipeline work

### 4. Migration Strategy

**Phase 1**: Migrate floe-core CLI from argparse to Click
- Rewrite `floe_core/cli/main.py` with Click groups
- Add Click dependency to floe-core
- Maintain backward compatibility with existing commands

**Phase 2**: Migrate RBAC from floe-cli to floe-core
- Move `floe-cli/src/floe_cli/commands/rbac.py` to `floe_core/cli/rbac/`
- Keep logic, change bindings to new group structure
- Update imports

**Phase 3**: Deprecate floe-cli
- Remove from workspace dependencies
- Archive package

## Consequences

### Positive

- **Single entry point** - `floe` always works regardless of install order
- **Consistent UX** - Click everywhere, same argument patterns
- **Extensible** - Click groups support future command additions
- **Better help** - Click's help formatting, command discovery
- **Epic 3B unblocked** - Can add `--enforcement-report` to `floe platform compile`

### Negative

- **Migration effort** - Rewrite existing argparse commands
- **Breaking changes** - Users of current `floe compile` may need adjustment
- **Package changes** - floe-cli deprecated (users must update dependencies)

### Neutral

- Click is industry standard for Python CLIs (dbt, Dagster, Prefect all use it)
- floe-core grows slightly larger (CLI code added)
- Learning curve minimal (Click well-documented)

## Target Directory Structure

```
packages/floe-core/
└── src/floe_core/cli/
    ├── __init__.py             # Export main()
    ├── main.py                 # @click.group() root
    ├── platform/               # Platform team commands
    │   ├── __init__.py
    │   ├── compile.py          # floe platform compile
    │   ├── test.py             # floe platform test
    │   ├── publish.py          # floe platform publish
    │   ├── deploy.py           # floe platform deploy
    │   └── status.py           # floe platform status
    ├── rbac/                   # RBAC management (migrated from floe-cli)
    │   ├── __init__.py
    │   ├── generate.py
    │   ├── validate.py
    │   ├── audit.py
    │   └── diff.py
    └── data/                   # Data team commands
        ├── __init__.py
        ├── compile.py          # floe compile
        ├── validate.py         # floe validate
        ├── run.py              # floe run
        └── test.py             # floe test
```

## References

- [ARCHITECTURE-SUMMARY.md](../ARCHITECTURE-SUMMARY.md) - Target CLI commands (lines 223-242)
- [platform-artifacts.md](../platform-artifacts.md) - Comprehensive CLI specification
- [ADR-0018: Opinionation Boundaries](0018-opinionation-boundaries.md) - Platform vs Data team model
- Epic 3B: Policy Validation Enhancement - Blocked by CLI conflict
- Epic 11: CLI Unification - Implements this ADR
