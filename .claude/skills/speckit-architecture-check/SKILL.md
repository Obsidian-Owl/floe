# SpecKit Architecture Check Skill

Technology boundary and layer compliance validation.

## When to Use

- When modifying files in core packages
- When adding cross-package imports
- Before creating a PR
- When the architecture-drift hook detects warnings

## Architecture Rules

### Technology Ownership (NON-NEGOTIABLE)

| Technology | Owns | Python Code MUST NOT |
|------------|------|---------------------|
| **dbt** | SQL compilation, dialect translation | Parse, validate, or transform SQL |
| **Dagster** | Orchestration, assets, schedules | Execute SQL directly |
| **Iceberg** | Storage format, ACID, time travel | Define orchestration |
| **Polaris** | Catalog, namespace management | Write to storage directly |
| **Cube** | Semantic layer, consumption APIs | Execute SQL, orchestrate |

### Four-Layer Model

```
Layer 1: FOUNDATION     → PyPI packages, plugin interfaces
Layer 2: CONFIGURATION  → OCI artifacts (manifest.yaml)
Layer 3: SERVICES       → K8s Deployments (Dagster, Polaris, Cube)
Layer 4: DATA           → K8s Jobs (dbt run, dlt ingestion)
```

**Rule**: Configuration flows DOWNWARD ONLY (1→2→3→4)
**FORBIDDEN**: Layer 4 modifying Layer 2 configuration

### Contract Boundaries

**CompiledArtifacts is the SOLE contract between packages**

```python
# CORRECT - floe-core produces
artifacts = compile_spec(spec)
artifacts.to_json_file("target/compiled_artifacts.json")

# CORRECT - other packages consume
artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")

# FORBIDDEN - passing FloeSpec across packages
def create_assets(spec: FloeSpec):  # NO!
    ...
```

## Execution Protocol

### Step 1: Identify Changed Packages

```bash
# Find which packages have changes
git diff --name-only HEAD~1..HEAD | grep -E '^packages/|^plugins/' | cut -d/ -f1-2 | sort -u
```

### Step 2: Check Technology Ownership

For each Python file, verify:

```bash
# Check for SQL parsing in non-dbt packages
rg "(sqlparse|sql.*parse|parse.*sql)" {file}

# Check for direct SQL execution in Dagster
rg "(cursor\.execute|connection\.execute)" packages/floe-dagster/
```

### Step 3: Check Layer Boundaries

```bash
# Check for Layer 4 modifying Layer 2
rg "(manifest\.yaml|write.*manifest)" packages/*/jobs/
rg "(manifest\.yaml|write.*manifest)" charts/floe-jobs/
```

### Step 4: Check Contract Usage

```bash
# Find direct FloeSpec usage outside floe-core
rg "from floe_core.* import.*FloeSpec" packages/ --ignore packages/floe-core/
rg "FloeSpec\(" packages/ --ignore packages/floe-core/
```

### Step 5: Run Architecture Drift Script

```bash
./scripts/check-architecture-drift
```

## Compliance Matrix

| Check | Command | Blocking? |
|-------|---------|-----------|
| SQL parsing outside dbt | `rg "sqlparse" packages/` | YES |
| Layer 4→2 modification | `check-architecture-drift` | YES |
| Direct FloeSpec usage | `rg "FloeSpec\(" --ignore floe-core` | YES |
| Plugin hardcoded secrets | `rg "password\s*=" plugins/` | YES |
| Missing entry points | Check pyproject.toml | NO |
| Cross-package test in package | Check imports | NO |

## Output Format

```markdown
## Architecture Check: {scope}

### Status: COMPLIANT | VIOLATION | WARNING

### Technology Ownership
- dbt boundary: PASS/FAIL
- Dagster boundary: PASS/FAIL
- Iceberg boundary: PASS/FAIL

### Layer Compliance
- Layer 4→2 check: PASS/FAIL
- Configuration flow: PASS/FAIL

### Contract Compliance
- CompiledArtifacts usage: PASS/FAIL
- FloeSpec isolation: PASS/FAIL

### Violations (MUST FIX)
1. {file}:{line} - {violation description}

### Warnings (SHOULD FIX)
1. {file}:{line} - {warning description}

### Recommendations
1. {improvement suggestion}
```

## Integration Points

### Hook: PostToolUse

Architecture drift is checked automatically on Edit/Write via hook:
```json
{
  "matcher": "Write|Edit",
  "command": "./scripts/check-architecture-drift \"$FILE_PATH\""
}
```

### Skill: speckit-test-review

Invokes architecture-compliance agent for deep analysis.

### Pre-PR Gate

Must pass before `gh pr create` is allowed.
