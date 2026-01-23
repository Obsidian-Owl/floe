---
name: speckit-verify-integration
description: Verify features are integrated into the floe system - reachable from CLI, plugin registry, or package exports. Use before PR to ensure features connect to the system.
user_invocable: true
---

## User Input

```text
$ARGUMENTS
```

You **MAY** consider the user input for scope filtering (if not empty).

## Overview

Quick verification that implemented features are reachable from system entry points. This prevents orphaned code that builds but isn't accessible.

**Use this skill:**
- Before `/speckit.pr` (recommended, not mandatory)
- After completing integration-focused tasks
- When reviewing an epic for completeness

## Constitution Alignment

This skill supports:
- **IV. Contract-Driven Integration**: Verifies new code connects to CompiledArtifacts or package exports
- **II. Plugin-First Architecture**: Confirms plugins register entry points
- **VII. Four-Layer Architecture**: Ensures code is reachable through proper layers

## What It Checks

**floe entry points:**
1. CLI commands (`floe_core/cli/` or `floe_cli/`)
2. Plugin registry (entry points in `pyproject.toml`)
3. Package `__all__` exports
4. CompiledArtifacts schema fields

**For each new component, verify:**
- Imported by at least one other file in `src/` (not just tests)
- Has a path to an entry point (CLI, plugin, or public API)

## Outline

1. **Identify Recent Changes**
   ```bash
   # Get files changed since branching from main
   git diff main --name-only --diff-filter=A -- '*.py' | grep '/src/'
   ```

2. **Check Import Reachability**
   For each new Python module in `src/`:
   - Search for imports of that module elsewhere in `src/`
   - Verify at least one non-test file imports it

3. **Check Plugin Entry Points**
   If new plugins were added:
   - Verify entry points in `pyproject.toml`
   - Verify discoverable via:
     ```python
     from importlib.metadata import entry_points
     eps = entry_points(group="floe.{plugin_type}")
     ```

4. **Check Schema Integration**
   If new Pydantic models were added:
   - Verify they're exported from package `__init__.py` or `__all__`
   - If they should be in CompiledArtifacts, verify inclusion

5. **Report Results**

## Quick Manual Check

```bash
# For recently added files, verify they're imported somewhere
for f in $(git diff main --name-only --diff-filter=A -- '*.py' | grep '/src/'); do
  module=$(basename "$f" .py)
  echo "Checking $module..."
  count=$(grep -r "from.*import.*$module\|import.*$module" . --include="*.py" | grep -v test | grep -v __pycache__ | wc -l)
  if [ "$count" -eq 0 ]; then
    echo "  WARNING: $module not imported anywhere (except tests)"
  else
    echo "  OK: imported in $count location(s)"
  fi
done
```

## Report Format

```markdown
## Integration Check Report

### New Modules
| Module | Imported By | Status |
|--------|-------------|--------|
| `floe_core/oci/layers.py` | `oci/client.py` | OK |
| `floe_core/utils/helpers.py` | (tests only) | WARNING |

### Plugin Entry Points
| Plugin | Entry Point Group | Registered |
|--------|-------------------|------------|
| `DuckDBComputePlugin` | `floe.computes` | OK |

### New Schemas
| Schema | Exported | In CompiledArtifacts |
|--------|----------|---------------------|
| `ValidationResult` | OK | N/A (internal) |

### Summary
- OK: 5 modules integrated
- WARNING: 1 module only imported by tests (review if intentional)
- ERROR: 0 unreachable modules

### Recommendations
- `floe_core/utils/helpers.py`: Consider adding to `__all__` or removing if unused
```

## Error Handling

| Issue | Severity | Action |
|-------|----------|--------|
| Module not imported anywhere | WARNING | Review if intentional (might be future use) |
| Plugin missing entry point | ERROR | Add to `pyproject.toml` before PR |
| Schema not exported | WARNING | Add to `__all__` or document why internal |

## Handoff

- **If errors found**: Fix before `/speckit.pr`
- **If warnings only**: Document in PR description why intentional
- **If clear**: Proceed to `/speckit.pr`

## References

- **[Plugin Architecture](../../../docs/architecture/plugin-system/index.md)** - Entry point patterns
- **[Component Ownership](../../rules/component-ownership.md)** - Package boundaries
- **[speckit.integration-check](../speckit-integration-check/SKILL.md)** - Contract stability (different focus)
