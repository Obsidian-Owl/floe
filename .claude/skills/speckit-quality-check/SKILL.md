# SpecKit Quality Check Skill

Post-task quality validation ensuring implementation meets quality standards.

## When to Use

- After completing any task implementation
- Before marking a Linear task as Done
- As part of the verification loop in epic-auto-mode

## Quality Checklist

### Code Quality

```
[ ] Type hints on ALL functions (mypy --strict passes)
[ ] Docstrings on all public functions (Google-style)
[ ] No hardcoded secrets (use SecretStr, environment variables)
[ ] No dangerous constructs (use safe alternatives)
[ ] Error handling with specific exceptions (no bare except)
[ ] Logging uses structlog (no print statements)
```

### Test Quality

```
[ ] Tests exist for new functionality
[ ] Tests have @pytest.mark.requirement() markers
[ ] Tests cover positive AND negative paths
[ ] No time.sleep() - use polling utilities
[ ] No pytest.skip() - tests must FAIL if infrastructure missing
[ ] Test isolation verified (unique namespaces, no global state)
```

### Architecture Compliance

```
[ ] Technology ownership respected:
    - dbt owns SQL (Python doesnt parse/validate SQL)
    - Dagster owns orchestration
    - Iceberg owns storage format
    - Polaris owns catalog
[ ] Layer boundaries respected (configuration flows 1-2-3-4)
[ ] CompiledArtifacts used for cross-package contracts
[ ] Plugin patterns followed (entry points, ABC inheritance, PluginMetadata)
```

### Security

```
[ ] Input validation with Pydantic
[ ] Parameterized queries (no SQL string formatting)
[ ] Safe subprocess (shell=False)
[ ] No secrets in logs
[ ] HTTPS/TLS for external connections
```

## Execution Protocol

### Step 1: Gather Files Changed

```bash
# Get files changed in current task
git diff --name-only HEAD~1..HEAD | grep '.py$'
```

### Step 2: Run Automated Checks

```bash
# Type checking
mypy --strict {changed_files}

# Linting
ruff check {changed_files}

# Security scan (if Aikido available)
aikido_full_scan {changed_files}
```

### Step 3: Invoke Quality Agents

For each changed file, spawn appropriate agents:

- Test files: test-edge-case-analyzer, test-isolation-checker
- Source files: code-pattern-reviewer-low, docstring-validator

### Step 4: Compile Results

Aggregate findings from all agents and automated checks.

## Output Format

```markdown
## Quality Check: {task_id}

### Status: PASS | NEEDS WORK | BLOCKED

### Summary
- Files checked: N
- Issues found: N (N critical, N warning)
- Tests added: N
- Coverage delta: +X%

### Critical Issues (must fix)
1. {issue with file:line}

### Warnings (should fix)
1. {issue with file:line}

### Recommendations
1. {improvement suggestion}
```
