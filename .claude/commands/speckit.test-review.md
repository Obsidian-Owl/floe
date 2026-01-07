---
description: Review test quality, coverage, and compliance before PR creation (read-only analysis)
handoffs:
  - label: "Commit changes"
    agent: git-commit
    prompt: "Tests reviewed. Commit changes?"
    send: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Perform a comprehensive pre-PR test quality review that validates:
- Test quality standards (no skips, no hardcoded sleep, type hints, docstrings)
- Requirement traceability (100% marker coverage expected)
- Security (no hardcoded secrets)
- Contract regression (package interfaces stable)
- Architecture compliance (framework patterns, not pipeline tests)
- Directory structure (package vs root placement)

This command runs **ONLY on changed test files** in the current feature branch and provides **informational feedback** to guide remediation.

## Operating Constraints

**STRICTLY READ-ONLY**: Do **not** modify any files. Output a structured findings report. This is an analysis tool, not a blocking gate.

**Architecture Focus**: This command validates **framework testing patterns** (plugin interfaces, contracts, compilation logic), NOT data pipeline testing (SQL transformations, business metrics). Exception: `demo/tests/` are intentionally pipeline tests.

**Git-Aware**: Only analyzes test files changed vs base branch (default: `main`). If not in git repo or no changed files, gracefully inform user.

**Target State ONLY**: This command validates the post-nuclear-delete testing structure (no legacy Docker Compose, K8s-native, contract tests at root level).

## Execution Steps

### Phase 0: Git Context Detection (5s)

**Verify git repository and branch:**

1. Run `git rev-parse --abbrev-ref HEAD` to get current branch name
2. If not on `main` or `master`, proceed; otherwise warn: "Already on main branch - switch to feature branch first"
3. Run `git diff --name-only main...HEAD | grep 'tests.*\.py$'` to identify changed test files
4. If no changed test files, inform user: "No changed test files detected. Nothing to review."
5. Extract changed packages by parsing file paths: `packages/{package-name}/tests/...`

**Output**: List of changed test files and affected packages.

### Phase 1: Test Quality Checks (10-15s)

**For each changed test file, run validation checks using `testing.traceability`:**

You MUST use the traceability module programmatically, NOT via subprocess. Import and call directly:

```python
from pathlib import Path
from testing.traceability.checks import TestQualityChecker

checker = TestQualityChecker()
issues = checker.check_file(Path("path/to/test_file.py"))
```

**CRITICAL checks (MUST pass):**
- **FAIL-001**: No `pytest.skip()` or `@pytest.mark.skip` (except `importorskip`, platform checks)
- **FAIL-002**: No `time.sleep()` (use `wait_for_condition()`)
- **FAIL-003**: All tests have `@pytest.mark.requirement("TR-XXX")`
- **FAIL-004**: All tests have docstrings (>10 chars)
- **FAIL-005**: Type hints on test functions (`-> None`)

**MAJOR checks (should pass):**
- **FAIL-006**: Float comparisons use `pytest.approx()`
- **FAIL-010**: No hardcoded `localhost` (use `self.get_service_host()`)
- **DIR-002**: Tests in correct tier directory (unit/contract/integration/e2e)
- **DIR-003**: Integration tests inherit from `IntegrationTestBase`

**MINOR checks (quality improvements):**
- **QUAL-001**: Duplicate string literals (3+ occurrences)

**Aggregate all issues** from all changed files.

### Phase 2: Security & Code Quality (5s)

**For each changed test file:**

- **SEC-001**: No hardcoded secrets (passwords, API keys, tokens)
  - Check for patterns: `password = "..."`, `api_key = "..."`, `secret = "..."`
  - Exclude: `test`, `mock`, `fake`, `placeholder`, `example` in value

**Aggregate security findings.**

### Phase 3: Requirement Traceability (5-10s)

**Calculate requirement coverage across ALL changed test files:**

```python
from testing.traceability.parser import TestFileParser

parser = TestFileParser()
total_tests = 0
tests_with_markers = 0

for file_path in changed_files:
    functions = parser.parse_file(file_path)
    for func in functions:
        total_tests += 1
        if func.requirement_markers:
            tests_with_markers += 1

coverage_percent = (tests_with_markers / total_tests) * 100.0
```

**Report**:
- Total test functions analyzed
- Tests with `@pytest.mark.requirement()` markers
- Coverage percentage (100% expected)
- List of files missing markers (if any)

### Phase 4: Contract Regression Check (5-10s)

**Run contract tests to detect breaking changes:**

Contract tests validate that package interfaces (CompiledArtifacts, plugin ABCs) remain stable.

```python
from testing.traceability.contracts import ContractTestRunner

runner = ContractTestRunner()
result = runner.run_contract_tests(timeout=60)

if not result.passed:
    print(f"CRITICAL: {result.failed_tests} contract tests FAILED (BREAKING CHANGE)")
    for failure in result.failures:
        print(f"  - {failure}")
```

**Contract tests location**: `tests/contract/` (ROOT level, not package level)

**Expected tests**:
- `test_compiled_artifacts_schema.py` - Schema stability
- `test_core_to_dagster_contract.py` - Integration contract
- `test_core_to_dbt_contract.py` - Profile contract
- `test_golden_artifacts.py` - Backwards compatibility

**Failure = CRITICAL regression** (breaking change in package interfaces).

### Phase 5: Architecture Compliance (5-10s)

**Validate architecture compliance for changed files:**

- **ARCH-001**: No data pipeline logic (SQL transformations, business metrics)
  - Check for: `SELECT ... FROM`, `CREATE TABLE`, `revenue`, `profit`, `conversion_rate`
  - Exception: `demo/tests/` are allowed to have pipeline tests

- **ARCH-002**: Technology ownership boundaries (no cross-component violations)
  - No SQL parsing in Python (dbt owns SQL)
  - No manual catalog operations (Polaris owns catalog)

- **ARCH-003**: Contract-driven integration (use `CompiledArtifacts`, not `FloeSpec`)

**Aggregate architecture findings.**

### Phase 6: Report Generation (1s)

**Generate structured findings report:**

```python
from testing.traceability.models import TestReviewReport, SummaryMetrics, RequirementCoverage

report = TestReviewReport(
    branch_name=current_branch,
    changed_files=changed_files,
    changed_packages=changed_packages,
    summary=SummaryMetrics(...),
    issues=all_issues,
    requirement_coverage=RequirementCoverage(...),
    contract_test_output=contract_result.output,
    contract_tests_passed=contract_result.passed
)

# Output markdown
print(report.to_markdown())
```

**Markdown report format**:

```markdown
## Test Quality Review Report

**Branch**: feature/polaris-oauth2-auth
**Changed Tests**: 8 files
**Changed Packages**: floe-polaris

### Summary

| Metric | Value |
|--------|-------|
| Total Issues | 5 |
| CRITICAL | 2 |
| MAJOR | 2 |
| MINOR | 1 |
| Requirement Coverage | 83.3% (10/12) |
| Regressions Detected | 0 |

### Findings

| ID | Category | Severity | Location | Summary | Remediation |
|----|----------|----------|----------|---------|-------------|
| T001 | Test Standards | CRITICAL | packages/floe-polaris/tests/integration/test_oauth2.py:45 | Skipped test detected | Replace pytest.skip() with pytest.fail(). See: .claude/rules/testing-standards.md#tests-fail-never-skip |
| ... | ... | ... | ... | ... | ... |

### Requirement Traceability

**Coverage**: 83.3% (10 of 12 tests have markers)

Missing markers:
- packages/floe-polaris/tests/integration/test_oauth2.py
- packages/floe-polaris/tests/integration/test_token_refresh.py

### Contract Regression Check

**Result**: ✅ All contracts pass (no breaking changes)

### Next Steps

1. **Fix CRITICAL issues** (2 findings)
2. **Address MAJOR issues** (2 findings)
3. **Optional improvements** (1 finding)
4. **Ready to proceed**: Once CRITICAL issues resolved, commit and create PR
```

**Total execution time**: 40-60 seconds

## Examples

### Example 1: Clean Review (No Issues)

```
User: /speckit.test-review