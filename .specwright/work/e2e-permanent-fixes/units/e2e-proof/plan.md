# Plan: E2E Proof (Unit 9)

## Task Breakdown

### Task 1: E2E test — thin loader happy path (AC-1)

Full pipeline E2E with thin definitions.py. Materialize, verify Iceberg data with strong assertions.

**File change map:**
- CREATE or MODIFY `tests/e2e/test_runtime_loader_e2e.py`

**Acceptance criteria:** AC-1

### Task 2: E2E test — loud failure scenarios (AC-2, AC-3, AC-4)

Three failure scenario tests: Polaris down, broken ingestion, module-load resilience.

**File change map:**
- CREATE `tests/e2e/test_loud_failure_e2e.py`

**Acceptance criteria:** AC-2, AC-3, AC-4

### Task 3: E2E test — S3 endpoint integrity (AC-5)

Verify S3 endpoint flows from manifest through to PyIceberg FileIO without corruption.

**File change map:**
- CREATE or MODIFY `tests/e2e/test_s3_endpoint_e2e.py`

**Acceptance criteria:** AC-5

### Task 4: E2E test — credential consistency (AC-6)

Verify no credential drift across manifest, K8s secrets, fixtures, and Helm values.

**File change map:**
- CREATE `tests/e2e/test_credential_consistency_e2e.py`

**Acceptance criteria:** AC-6

### Task 5: Regression run (AC-7)

Full `make test-e2e` regression pass. No new tests — just verification all existing E2E tests pass.

**File change map:**
- No file changes. Run existing test suite.

**Acceptance criteria:** AC-7

## Task Dependencies

```
Tasks 1-4 are independent (can be parallel)
Task 5 depends on all of 1-4 (regression after all new E2E tests added)
```

## Notes
- All E2E tests run via `make test-e2e` in Kind cluster
- Each test MUST have `@pytest.mark.requirement()` tracing to audit finding
- Strong assertions throughout — row counts, error message content, exact values
- No `time.sleep()` — use polling utilities from `testing/fixtures/services.py`
