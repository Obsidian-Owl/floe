# SQL Linting Requirements (REQ-096 to REQ-100)

**Domain**: 01 - Plugin Architecture
**Plugin Type**: DBTPlugin (Entry Point: `floe.dbt`)
**Related ADR**: ADR-0043 (dbt Compilation Environment Abstraction)
**Epic**: Epic 3 (Plugin Interface Extraction)

---

## REQ-096: SQL Linting Method in DBTPlugin

**ID**: REQ-096
**Title**: DBTPlugin SHALL provide lint_project() method
**Type**: FR (Functional Requirement)
**Priority**: P2 (High)
**Status**: Approved

### Requirement Statement

The DBTPlugin ABC SHALL include a `lint_project()` abstract method that returns dialect-aware SQL validation results via `ProjectLintResult`.

### Acceptance Criteria

1. Method signature matches:
   ```python
   def lint_project(
       self,
       project_dir: Path,
       profiles_dir: Path,
       target: str,
       fix: bool = False,
   ) -> ProjectLintResult
   ```
2. Returns `ProjectLintResult` with all detected linting issues
3. Supports `fix=True` for auto-correction if linter supports it
4. Raises `DBTLintError` if linting process fails (not if SQL has issues)
5. Contract tests validate method signature across all implementations

### Rationale

Platform teams need SQL validation at compile-time to enforce code quality standards before deployment.

### Traceability

- **ADR**: ADR-0043 (dbt Compilation Environment Abstraction)
- **Architecture**: `plugin-architecture.md` (DBTPlugin section)
- **Test Spec**: `tests/contract/test_dbt_compilation_plugin.py`

### Related Requirements

- REQ-097: SQLFluff Integration
- REQ-098: Fusion Static Analysis
- REQ-099: Platform Configuration
- REQ-100: Pre-Compilation Hook

---

## REQ-097: SQLFluff Integration for LocalDBTPlugin

**ID**: REQ-097
**Title**: LocalDBTPlugin SHALL use SQLFluff for SQL linting
**Type**: FR (Functional Requirement)
**Priority**: P2 (High)
**Status**: Approved

### Requirement Statement

The LocalDBTPlugin implementation SHALL delegate SQL linting to SQLFluff with dialect auto-detection from profiles.yml.

### Acceptance Criteria

1. Detects SQL dialect from profiles.yml target (duckdb, snowflake, bigquery, redshift, databricks, postgres, spark)
2. Invokes SQLFluff CLI with correct `--dialect` flag
3. Parses SQLFluff JSON output (`--format=json`) into `ProjectLintResult`
4. Maps SQLFluff severity levels (WARNING, ERROR) to `LintSeverity` enum
5. Supports auto-fix via `--fix` flag when `fix=True`
6. Returns empty `ProjectLintResult` if SQLFluff not installed (logs warning)
7. Reads `.sqlfluff` config file if exists in project root
8. Allows platform team to override SQLFluff rules in `manifest.yaml`

### Implementation Notes

**Dialect Mapping** (profiles.yml adapter → SQLFluff dialect):
- `duckdb` → `duckdb`
- `snowflake` → `snowflake`
- `bigquery` → `bigquery`
- `redshift` → `redshift`
- `databricks` → `databricks`
- `postgres` → `postgres`
- `spark` → `sparksql`

**SQLFluff Invocation**:
```python
subprocess.run([
    "sqlfluff",
    "lint",
    f"--dialect={dialect}",
    "--format=json",
    str(project_dir / "models"),
], capture_output=True, text=True)
```

### Rationale

SQLFluff is proven, open-source, supports all 7 SQL dialects floe targets.

### Traceability

- **ADR**: ADR-0043
- **Test Spec**: `plugins/floe-dbt-local/tests/integration/test_sqlfluff_linting.py`

### Related Requirements

- REQ-096: lint_project() ABC
- REQ-099: Platform Configuration

---

## REQ-098: Static Analysis Integration for DBTFusionPlugin

**ID**: REQ-098
**Title**: DBTFusionPlugin SHALL use built-in static analysis for SQL validation
**Type**: FR (Functional Requirement)
**Priority**: P2 (High - Fusion is immediate priority)
**Status**: Approved

### Requirement Statement

The DBTFusionPlugin implementation SHALL leverage dbt Fusion's built-in static analysis during `dbtf compile` for dialect-aware SQL validation.

### Acceptance Criteria

1. Invokes `dbtf compile` via CLI subprocess
2. Parses stderr output for SQL validation errors/warnings
3. Extracts file path, line number, column, error message from Fusion output
4. Maps Fusion validation issues to `ProjectLintResult` format
5. Returns validation results even if compile partially succeeds
6. Indicates via `supports_sql_linting() -> True`
7. Performance: Linting adds <10% overhead (Fusion 30x faster parsing)

### Implementation Notes

**dbt Fusion Static Analysis** ([source](https://docs.getdbt.com/docs/fusion/new-concepts)):
- Fusion "fully comprehends your project's SQL"
- Performs "dialect-aware validation" during compilation
- Validates SQL against warehouse schema (column existence, types)
- Built-in linting eliminates need for external linter (SQLFluff)

**Invocation**:
```python
result = subprocess.run([
    "dbtf",
    "compile",
    "--project-dir", str(project_dir),
    "--profiles-dir", str(profiles_dir),
    "--target", target,
], capture_output=True, text=True, check=False)

# Parse stderr for validation errors
issues = parse_fusion_errors(result.stderr)
```

### Rationale

dbt Fusion's Rust-based static analysis provides superior performance and dialect-aware validation without external dependencies.

### Traceability

- **ADR**: ADR-0043
- **Research**: [dbt Fusion New Concepts](https://docs.getdbt.com/docs/fusion/new-concepts), [Meet the dbt Fusion Engine](https://docs.getdbt.com/blog/dbt-fusion-engine)
- **Test Spec**: `plugins/floe-dbt-fusion/tests/integration/test_fusion_linting.py`

### Related Requirements

- REQ-096: lint_project() ABC
- REQ-099: Platform Configuration

---

## REQ-099: Platform-Configurable Linting Enforcement

**ID**: REQ-099
**Title**: Platform team SHALL configure SQL linting enforcement level
**Type**: FR (Functional Requirement)
**Priority**: P2 (High)
**Status**: Approved

### Requirement Statement

The `manifest.yaml` SHALL allow platform teams to configure SQL linting enforcement level (error/warning/disabled) and linting rules.

### Acceptance Criteria

1. Configuration schema supports `sql_linting.enforcement` with values: `error`, `warning`, `disabled`
2. Configuration schema supports `sql_linting.rules` for linter-specific rules
3. Default enforcement level is `warning` (log issues, don't block)
4. Linting can be fully disabled via `sql_linting.enabled: false`
5. Data team CANNOT override platform team's enforcement level (enforced via compilation)
6. Schema validation rejects invalid enforcement values

### Configuration Schema

```yaml
plugins:
  dbt_compiler:
    provider: fusion  # or local, or cloud
    config:
      sql_linting:
        enabled: true
        enforcement: warning  # error | warning | disabled
        rules:  # Linter-specific configuration
          max_line_length: 100
          indentation: 2
          # SQLFluff-specific (when provider: local)
          sqlfluff_config_path: .sqlfluff  # Optional override
```

### Enforcement Behavior

| Level | Behavior | Use Case |
|-------|----------|----------|
| `error` | Fail compilation on linting errors (warnings allowed) | Strict governance, production |
| `warning` | Log linting issues, continue compilation | Gradual adoption, development |
| `disabled` | Skip linting entirely | Legacy projects, emergency bypass |

### Rationale

Platform teams need control over code quality standards while allowing gradual adoption via warning mode.

### Traceability

- **ADR**: ADR-0043
- **Test Spec**: `tests/contract/test_platform_manifest_schema.py`

### Related Requirements

- REQ-096: lint_project() ABC
- REQ-097: SQLFluff Integration
- REQ-098: Fusion Static Analysis
- REQ-100: Pre-Compilation Hook

---

## REQ-100: Pre-Compilation Linting Hook in OrchestratorPlugin

**ID**: REQ-100
**Title**: OrchestratorPlugin SHALL invoke lint_project() before dbt compilation if enabled
**Type**: FR (Functional Requirement)
**Priority**: P3 (Medium)
**Status**: Approved

### Requirement Statement

The OrchestratorPlugin implementation SHALL invoke `DBTPlugin.lint_project()` before model compilation if `sql_linting.enabled == true`.

### Acceptance Criteria

1. Linting executes BEFORE `compile_project()` or `run_models()`
2. If `enforcement == "error"` and linting errors exist, raise `CompilationError` with lint results
3. If `enforcement == "warning"`, log lint results and continue
4. If `enforcement == "disabled"`, skip linting
5. Attach lint results as orchestrator metadata (e.g., Dagster asset metadata)
6. Linting errors include file path, line number, rule code, message

### Orchestrator Integration Example (Dagster)

```python
from floe_core.plugin_interfaces import DBTPlugin
from floe_core.errors import CompilationError

@asset
def customers(context, dbt_compiler: DBTPlugin):
    """Compile and run customers model with SQL linting."""

    # 1. Lint if enabled
    if platform_config.sql_linting.enabled:
        lint_result = dbt_compiler.lint_project(
            project_dir=context.project_dir,
            profiles_dir=context.profiles_dir,
            target=context.target,
        )

        # 2. Attach metadata
        context.add_output_metadata({
            "lint_errors": lint_result.errors,
            "lint_warnings": lint_result.warnings,
            "lint_issues": [
                f"{issue.file_path}:{issue.line} - {issue.message}"
                for issue in lint_result.issues[:10]  # First 10
            ],
        })

        # 3. Enforce
        if platform_config.sql_linting.enforcement == "error" and not lint_result.passed:
            raise CompilationError(
                f"SQL linting failed with {lint_result.errors} errors. "
                f"Fix issues or set enforcement=warning to continue."
            )

    # 4. Compile
    manifest = dbt_compiler.compile_project(
        project_dir=context.project_dir,
        profiles_dir=context.profiles_dir,
        target=context.target,
    )
```

### Rationale

Early linting prevents invalid SQL from reaching compilation/execution, reducing feedback loop.

### Traceability

- **ADR**: ADR-0043
- **Test Spec**: `plugins/floe-orchestrator-dagster/tests/integration/test_linting_hook.py`

### Related Requirements

- REQ-096: lint_project() ABC
- REQ-099: Platform Configuration

---

## Summary: Requirements Traceability

| Requirement | Title | Priority | ADR | Test Spec |
|-------------|-------|----------|-----|-----------|
| REQ-096 | lint_project() method | P2 | ADR-0043 | tests/contract/test_dbt_compilation_plugin.py |
| REQ-097 | SQLFluff integration | P2 | ADR-0043 | plugins/floe-dbt-local/tests/integration/test_sqlfluff_linting.py |
| REQ-098 | Fusion static analysis | P2 | ADR-0043 | plugins/floe-dbt-fusion/tests/integration/test_fusion_linting.py |
| REQ-099 | Platform configuration | P2 | ADR-0043 | tests/contract/test_platform_manifest_schema.py |
| REQ-100 | Pre-compilation hook | P3 | ADR-0043 | plugins/floe-orchestrator-dagster/tests/integration/test_linting_hook.py |

---

## Validation Criteria

SQL linting requirements are complete when:

- [ ] All 5 requirements documented with complete template fields
- [ ] `lint_project()` method added to DBTPlugin ABC
- [ ] LocalDBTPlugin.lint_project() implemented with SQLFluff
- [ ] DBTFusionPlugin.lint_project() implemented with static analysis
- [ ] Platform configuration schema supports `sql_linting` section
- [ ] OrchestratorPlugin integration demonstrates pre-compilation linting
- [ ] Contract tests validate linting method signatures
- [ ] Integration tests validate actual linting behavior
- [ ] ADR-0043 backref references requirements

---

## Notes

- **SQLFluff Dependency**: Optional dependency for LocalDBTPlugin (graceful degradation if not installed)
- **Fusion GA Timeline**: dbt Fusion public beta as of May 2025, expect GA within 6-12 months
- **Cloud Linting**: dbt Cloud linting API TBD - requires research (deferred to Epic 8)
