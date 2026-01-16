# Quality Gates

All quality gates run per iteration during automated implementation.

## Overview

Every agent iteration runs ALL gates. If any gate fails, the agent:
1. Logs the failure in activity.md
2. Attempts to fix (max 3 retries per gate)
3. If still failing, signals BLOCKED and creates a sub-task

## Gate 1: Lint (Ruff)

**Command**:
```bash
uv run ruff check . --fix
uv run ruff format .
```

**Pass Criteria**: Exit code 0

**What It Checks**:
- PEP 8 compliance
- Import sorting
- Unused imports/variables
- Code style consistency

**Auto-Fix**: Ruff can auto-fix many issues with `--fix`

## Gate 2: Type Check (mypy)

**Command**:
```bash
uv run mypy --strict packages/ plugins/
```

**Pass Criteria**: Exit code 0, no type errors

**What It Checks**:
- Type hint coverage (100% required with --strict)
- Type correctness
- Incompatible types
- Missing return statements

**Common Fixes**:
```python
# Missing type hints
def process(data):  # BAD
def process(data: dict[str, Any]) -> None:  # GOOD

# Optional vs None
def get_user(id: str) -> User:  # BAD if can return None
def get_user(id: str) -> User | None:  # GOOD
```

## Gate 3: Unit Tests (pytest)

**Command**:
```bash
uv run pytest tests/unit/ -v --tb=short
```

**Pass Criteria**: All tests pass, coverage >= 80%

**What It Checks**:
- Functional correctness
- Edge cases
- Error handling
- Requirement traceability

**Coverage Report**:
```bash
uv run pytest tests/unit/ --cov=src --cov-report=term-missing
```

## Gate 4: Security Review

**Command**:
```bash
/security-review
```

**Pass Criteria**: No HIGH or CRITICAL findings

**What It Checks**:
- Injection vulnerabilities (SQL, command, XSS)
- Authentication/authorization issues
- Data exposure (hardcoded secrets, PII logging)
- Cryptographic weaknesses
- Input validation gaps
- Code execution vulnerabilities

**Categories**:

| Severity | Action Required |
|----------|----------------|
| CRITICAL | Block commit, fix immediately |
| HIGH | Block commit, fix immediately |
| MEDIUM | Fix before PR |
| LOW | Document in PR, fix or accept |

**Common Security Patterns**:
```python
# Hardcoded secret - FORBIDDEN
api_key = "sk-..."
# CORRECT: Use SecretStr and environment variables
api_key = SecretStr(os.environ["API_KEY"])

# Shell command with user input - FORBIDDEN
subprocess.run(f"ls {user_input}", shell=True)
# CORRECT: Use list of args without shell
subprocess.run(["ls", user_input], shell=False)

# SQL string formatting - FORBIDDEN
cursor.run(f"SELECT * FROM users WHERE id = {id}")
# CORRECT: Use parameterized queries
cursor.run("SELECT * FROM users WHERE id = %s", (id,))
```

## Gate 5: Constitution Validation

**Command**:
```bash
python .ralph/scripts/validate-constitution.py --files $(git diff --name-only HEAD~1)
```

**Pass Criteria**: All 8 principles validated

**Principles Checked**:

### I. Technology Ownership
- No SQL parsing in Python
- dbt owns all SQL compilation
- No manual SQL dialect translation

```python
# FORBIDDEN - Python parsing SQL
def parse_sql(sql: str) -> dict: ...

# CORRECT - Let dbt handle SQL
def compile_dbt_models() -> Path:
    dbt.invoke(["compile"])
```

### II. Plugin-First Architecture
- Entry points used for plugin registration
- Plugin ABCs properly inherited
- PluginMetadata declared

### III. Enforced vs Pluggable
- Enforced: Iceberg, dbt, OTel, OpenLineage, K8s
- Pluggable: Compute, Orchestrator, Catalog, Semantic Layer

### IV. Contract-Driven Integration
- CompiledArtifacts as sole contract
- Pydantic v2 syntax (`@field_validator`, `model_config`)
- No ad-hoc integration formats

```python
# FORBIDDEN - Direct FloeSpec passing
def create_assets(spec: FloeSpec): ...

# CORRECT - Use CompiledArtifacts
def create_assets(artifacts: CompiledArtifacts): ...
```

### V. K8s-Native Testing
- No `time.sleep()` in tests
- IntegrationTestBase for integration tests
- All integration/E2E in Kind cluster

### VI. Security First
- SecretStr for credentials
- No dangerous dynamic code patterns
- Input validation with Pydantic

### VII. Four-Layer Architecture
- Layer 1 (Foundation) -> Layer 2 (Config) -> Layer 3 (Services) -> Layer 4 (Data)
- No cross-layer violations
- Configuration flows downward only

### VIII. Observability By Default
- OpenTelemetry traces
- OpenLineage events
- Structured logging with structlog

## Gate Execution Order

Gates run in dependency order:

```
1. lint      (fastest, catches syntax issues)
     |
     v
2. typecheck (catches type errors)
     |
     v
3. unit_tests (validates functionality)
     |
     v
4. security  (prevents vulnerabilities)
     |
     v
5. constitution (ensures architecture alignment)
```

## Failure Handling

### Per-Iteration Failure

```
Gate fails
    |
    v
Log failure in activity.md
    |
    v
Attempt fix (automatic where possible)
    |
    v
Re-run gate
    |
    +-- Pass? --> Continue to next gate
    |
    +-- Fail (retry 1)? --> Attempt different fix
    |
    +-- Fail (retry 2)? --> Attempt different fix
    |
    +-- Fail (retry 3)? --> Signal BLOCKED
                               |
                               v
                           Create sub-task
                               |
                               v
                           Continue with next subtask
```

### Activity Log Entry (Failure)

```markdown
## Iteration 5 - 2026-01-16T14:45:00Z

**Subtask**: T001.2 - Implement authentication middleware
**Status**: BLOCKED

### Gate Failures
- **security**: FAILED after 3 retries
  - Finding: Hardcoded API key in auth.py:45
  - Attempts: Replaced with env var (failed validation), used SecretStr (import error), fixed import
  - Resolution: Created sub-task T001.2.1 to fix dependency issue

### Created Sub-Task
- T001.2.1: Add pydantic-settings dependency for SecretStr
```

## CI Integration

Gates also run in CI after PR creation:

```yaml
# .github/workflows/ci.yml
jobs:
  quality:
    steps:
      - name: Lint
        run: uv run ruff check . && uv run ruff format --check .

      - name: Type Check
        run: uv run mypy --strict packages/ plugins/

      - name: Unit Tests
        run: uv run pytest tests/unit/ -v --tb=short

      - name: Security Scan
        uses: anthropics/claude-code-security-review@main
        with:
          path: .

      - name: Contract Tests
        run: uv run pytest tests/contract/ -v
```

## Configuration

See `.ralph/config.yaml`:

```yaml
quality_gates:
  per_iteration:
    - lint
    - typecheck
    - unit_tests
    - security
    - constitution

  pre_pr:
    - test_review        # /speckit.test-review
    - integration_check  # /speckit.integration-check
    - security_review    # /security-review (full)
    - arch_review        # /arch-review

  gate_config:
    lint:
      command: "uv run ruff check . --fix && uv run ruff format ."
      max_retries: 3
    typecheck:
      command: "uv run mypy --strict packages/ plugins/"
      max_retries: 2
    unit_tests:
      command: "uv run pytest tests/unit/ -v --tb=short"
      coverage_threshold: 80
      max_retries: 3
    security:
      command: "/security-review"
      block_on: ["CRITICAL", "HIGH"]
      max_retries: 3
    constitution:
      command: "python .ralph/scripts/validate-constitution.py"
      max_retries: 2
```

## Best Practices

1. **Run gates locally before commit**
   ```bash
   make check  # Runs all gates
   ```

2. **Fix lint issues first** - They're fastest to fix and often cause other gates to fail

3. **Address security findings immediately** - Don't defer to "later"

4. **Keep constitution validation current** - Update as architecture evolves

5. **Monitor gate duration** - Slow gates indicate test suite issues
