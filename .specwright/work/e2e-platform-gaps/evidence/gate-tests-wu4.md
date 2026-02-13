# Gate: Tests -- WU-4 Evidence

**Status**: WARN
**Findings**: BLOCK: 0, WARN: 5, INFO: 3

## Files Audited

| File | Tests | Role |
|------|-------|------|
| `testing/tests/unit/test_otel_pipeline.py` | 23 | Structural validation of OTel pipeline config |
| `tests/e2e/test_observability.py` | 8 | E2E observability stack integration |
| `tests/e2e/test_observability_roundtrip_e2e.py` | 3 | E2E trace round-trip validation |
| `tests/e2e/conftest.py` | N/A (fixtures) | `otel_tracer_provider` fixture (WU4-AC5) |

## WARN Findings

### WARN-1: Operator precedence bug in `test_conftest_imports_otlp_exporter` (line 431-434)

**File**: `testing/tests/unit/test_otel_pipeline.py`

The boolean expression has an operator precedence error that makes the check weaker than intended:

```python
has_otlp_exporter = (
    "OTLPSpanExporter" in content
    or "otlp" in content.lower() and "exporter" in content.lower()
)
```

Python evaluates `and` before `or`, so this parses as:

```python
("OTLPSpanExporter" in content) or ("otlp" in content.lower() and "exporter" in content.lower())
```

The first branch (`"OTLPSpanExporter" in content`) is correct and sufficient for the current implementation. However, the fallback branch is too permissive -- any file containing both the words "otlp" and "exporter" anywhere (e.g., in a comment, docstring, or unrelated context) would pass. The intended logic was likely:

```python
has_otlp_exporter = (
    "OTLPSpanExporter" in content
    or ("otlp" in content.lower() and "exporter" in content.lower())
)
```

**Impact**: Low in practice (the first branch works), but the fallback would accept false positives. A conftest that mentions "otlp" in a comment and "exporter" elsewhere would pass without actually importing OTLPSpanExporter.

**Recommendation**: Add explicit parentheses to the `or`/`and` expression, or remove the fallback entirely since the primary check is sufficient.

### WARN-2: `otel_tracer_provider` fixture defined but never consumed

**File**: `tests/e2e/conftest.py` (line 580-613)

The `otel_tracer_provider` fixture is defined and satisfies WU4-AC5 structurally, but no test function in the E2E suite actually requests it as a parameter. This means:

1. The fixture is never exercised during test runs.
2. If the fixture has a runtime bug (e.g., wrong endpoint, import error), it will not be caught.
3. The TracerProvider is never used to emit traces during E2E tests -- tests that need traces (like `test_compilation_generates_traces`) create their own TracerProvider inline instead.

**Impact**: Medium. The fixture exists (passes WU4-AC5 structurally) but is dead code. Tests that need tracing build their own providers, making this fixture redundant.

**Recommendation**: Either wire the fixture into at least one E2E test that validates trace emission, or document it as a session-scoped setup fixture with `autouse=True` if it should apply globally.

### WARN-3: Conditional no-op in `test_roundtrip_test_uses_correct_otel_label_if_present` (line 91-104)

**File**: `testing/tests/unit/test_otel_pipeline.py`

```python
if "app.kubernetes.io/component" in content:
    assert ...
```

If the roundtrip test file does NOT contain `app.kubernetes.io/component`, the test silently passes without asserting anything. A sloppy implementation that removes all label selectors from the roundtrip test would pass this test. The test should at minimum log or note that no label selectors were found, or the conditional should be inverted to assert the absence case explicitly.

**Impact**: Low. The test is a defensive check for a secondary file. The primary label check (test_observability_test_uses_correct_otel_label_selector) covers the critical case.

**Recommendation**: Add an explicit else branch or remove the conditional to make the test always assert.

### WARN-4: `test_service_names_aligned_across_e2e_tests` silently passes when one file has no service names (line 367-399)

**File**: `testing/tests/unit/test_otel_pipeline.py`

```python
if obs_real and rt_real:
    overlap = obs_real & rt_real
    assert len(overlap) > 0, ...
```

If either `obs_real` or `rt_real` is empty, the assertion is never reached and the test passes. This means if one E2E test file removes all Jaeger queries, the alignment test silently passes.

**Impact**: Medium. A regression that removes Jaeger queries from one test file would go undetected by this test.

**Recommendation**: Assert that both sets are non-empty before checking overlap, or remove the guard and always assert.

### WARN-5: E2E test `test_observability.py` line 429 uses correct label but lacks negative assertion

**File**: `tests/e2e/test_observability.py`

The label selector at line 429 correctly uses `app.kubernetes.io/component=otel` (satisfying WU4-AC1). However, the E2E test itself does not verify that the OLD label (`opentelemetry-collector`) is not present. The unit test suite (`test_otel_pipeline.py`) does cover the negative case via `test_observability_test_does_not_use_old_otel_label`, so this is covered indirectly.

**Impact**: Low. Already covered by the unit test suite.

## INFO Findings

### INFO-1: No `time.sleep()` found in any audited file

Confirmed clean. All files use `wait_for_condition()` polling utility from `testing.fixtures.polling`.

### INFO-2: No `pytest.skip()` found in any audited file

Confirmed clean. Infrastructure unavailability triggers `pytest.fail()` as required.

### INFO-3: Values.yaml OTel config uses Helm templating for Jaeger endpoint

The `otlp/jaeger` exporter endpoint is `"{{ .Release.Name }}-jaeger-collector:4317"` (Helm template). The unit test `test_jaeger_exporter_has_grpc_endpoint` checks for `:4317` in the raw YAML, which works because the template string contains the literal `:4317`. However, a change to the port variable (e.g., `{{ .Values.jaeger.port }}`) would break the test. This is acceptable because port 4317 is a hard architectural requirement (OTLP gRPC standard port).

## Quality Checklist Results

| Check | Result | Notes |
|-------|--------|-------|
| Assertion strength | PASS | Tests use exact value matching (`is True`, `in content`, `== 1`). No bare `is not None` on values that can't be None. |
| Requirement markers | PASS | All 23 unit tests have `@pytest.mark.requirement()`. All 8+3 E2E tests have requirement markers. |
| Docstrings | PASS | All 23 unit tests and all E2E tests have docstrings explaining intent. |
| Type hints | PASS | All test methods have `-> None` return type. Fixtures have return types. |
| Side-effect verification | N/A | These are structural/config validation tests (file parsing), not side-effect tests. No mocks are used. |
| No `time.sleep()` | PASS | None found in any audited file. |
| No `pytest.skip()` | PASS | None found in any audited file. |
| Edge cases | PASS (partial) | Tests cover both positive (correct label present) and negative (old label absent) cases. See WARN-3 and WARN-4 for conditional edge cases that could be stronger. |

## Coverage Map

| AC | Unit Tests (test_otel_pipeline.py) | E2E Tests | Verdict |
|----|-------------------------------------|-----------|---------|
| WU4-AC1: Label selector = `otel` | `test_configmap_otel_uses_correct_component_label`, `test_observability_test_uses_correct_otel_label_selector`, `test_observability_test_does_not_use_old_otel_label`, `test_roundtrip_test_uses_correct_otel_label_if_present` | `test_prometheus_metrics` (line 429) | COVERED |
| WU4-AC2: Jaeger exporter OTLP gRPC | `test_values_yaml_has_otlp_jaeger_exporter`, `test_jaeger_exporter_has_grpc_endpoint`, `test_jaeger_exporter_has_tls_insecure`, `test_traces_pipeline_includes_jaeger_exporter`, `test_otlp_receiver_enabled_with_grpc` | N/A (config validation) | COVERED |
| WU4-AC3: values-test.yaml enables Jaeger | `test_otel_enabled_in_test_values`, `test_jaeger_enabled_in_test_values`, `test_jaeger_all_in_one_enabled_in_test_values`, `test_otel_and_jaeger_both_enabled_simultaneously` | N/A (config validation) | COVERED |
| WU4-AC4: E2E verifies trace flow | `test_roundtrip_queries_jaeger_with_service_param`, `test_roundtrip_asserts_traces_non_empty`, `test_roundtrip_service_name_is_consistent`, `test_observability_test_queries_jaeger_with_service_param`, `test_service_names_aligned_across_e2e_tests` | `test_compilation_generates_traces`, `test_otel_traces_in_jaeger`, `test_otel_collector_accepts_spans`, `test_jaeger_query_api_functional` | COVERED |
| WU4-AC5: TracerProvider in conftest | `test_conftest_imports_tracer_provider`, `test_conftest_imports_otlp_exporter`, `test_conftest_has_tracer_provider_fixture`, `test_conftest_tracer_uses_batch_processor`, `test_conftest_tracer_sets_service_name` | Fixture exists (line 580-613) but unused (WARN-2) | COVERED (structurally) |

## Lazy Implementation Test

> Could a sloppy implementation pass these tests?

**Label alignment (WU4-AC1)**: No. Tests check both positive (correct label present) and negative (old label absent) in the actual source files. Hardcoding would require matching real file content.

**Jaeger exporter (WU4-AC2)**: No. Tests parse the actual `values.yaml` YAML and check specific keys (`otlp/jaeger`, `:4317`, `tls.insecure`, pipeline wiring). A partial implementation would fail at least one check.

**values-test.yaml (WU4-AC3)**: No. Tests check 4 specific conditions (`otel.enabled`, `jaeger.enabled`, `allInOne.enabled`, both simultaneously). Missing any one fails.

**E2E trace flow (WU4-AC4)**: Partially. The unit tests validate that E2E test SOURCE CODE contains the right patterns (queries Jaeger, asserts non-empty). A sloppy E2E test implementation that queries Jaeger but does not actually check span content would pass the unit-level source analysis. However, the actual E2E tests (`test_observability.py`, `test_observability_roundtrip_e2e.py`) DO validate span content at runtime.

**TracerProvider (WU4-AC5)**: Partially. The unit tests confirm the fixture exists in source code. But since the fixture is never consumed (WARN-2), a broken fixture (e.g., wrong import path) would not be caught until a test actually uses it.

## Verdict

**WARN** -- All 5 acceptance criteria have test coverage. No blocking issues found. Five warnings identified:

1. Operator precedence bug (cosmetic, primary branch works correctly)
2. Dead fixture (structurally present but never exercised at runtime)
3. Two conditional no-ops that silently pass on missing data
4. Missing negative assertion in E2E test (covered by unit test indirectly)

The test suite is well-structured with 23 focused unit tests covering all 5 ACs, strong assertions, proper requirement markers, docstrings, and type hints. The WARNs are hardening opportunities, not blocking gaps.
