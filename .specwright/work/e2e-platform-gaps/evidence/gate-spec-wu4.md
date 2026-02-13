# Gate: Spec -- WU-4 Evidence
**Status**: PASS (with WARN on NF-7 lint)

## AC Mapping

| AC | Status | Implementation | Test | Notes |
|----|--------|---------------|------|-------|
| WU4-AC1 | PASS | `tests/e2e/test_observability.py:429` uses `app.kubernetes.io/component=otel`; `charts/floe-platform/templates/configmap-otel.yaml:13` declares `app.kubernetes.io/component: otel` -- exact match | `TestOtelLabelAlignment` (4 tests) at `testing/tests/unit/test_otel_pipeline.py:44-104` -- all PASSED | Labels match exactly. Old label `opentelemetry-collector` confirmed absent from test file. |
| WU4-AC2 | PASS | `charts/floe-platform/values.yaml:342-345` defines `otlp/jaeger` exporter with endpoint `{{ .Release.Name }}-jaeger-collector:4317` and `tls.insecure: true`; line 352 wires it into traces pipeline `exporters: [debug, otlp/jaeger]` | `TestOtelJaegerExporter` (5 tests) at `testing/tests/unit/test_otel_pipeline.py:111-196` -- all PASSED | Exporter defined, uses gRPC 4317, TLS insecure, and wired into traces pipeline. |
| WU4-AC3 | PASS | `charts/floe-platform/values-test.yaml:206-207` sets `otel.enabled: true`; lines 230-235 set `jaeger.enabled: true` and `allInOne.enabled: true`; OTLP receiver ports inherited from `values.yaml:536-541` (`collector.otlp.grpc.port: 4317`) | `TestValuesTestOtelJaeger` (4 tests) at `testing/tests/unit/test_otel_pipeline.py:203-259` -- all PASSED | Both OTel and Jaeger enabled simultaneously. Jaeger allInOne includes OTLP receiver by default. |
| WU4-AC4 | PASS | `tests/e2e/test_observability_roundtrip_e2e.py:72-83` queries `GET /api/traces?service=floe-platform` and asserts `len(data.get("data", [])) > 0`; `tests/e2e/test_observability.py:87-104` does the same with `assert len(traces) > 0` | `TestE2EJaegerTraceQuery` (5 tests) at `testing/tests/unit/test_otel_pipeline.py:266-399` -- all PASSED | Both E2E test files query Jaeger with service parameter and assert non-empty data array. Service names aligned (`floe-platform` in both). |
| WU4-AC5 | PASS | `tests/e2e/conftest.py:580-613` defines `otel_tracer_provider` session fixture: `TracerProvider` with `Resource(service.name="floe-platform")`, `OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)`, `BatchSpanProcessor` | `TestE2EConftestTracerProvider` (5 tests) at `testing/tests/unit/test_otel_pipeline.py:406-511` -- all PASSED | Fixture uses correct endpoint (localhost:4317), correct service name (floe-platform), BatchSpanProcessor for non-blocking export. |

## Quality Checks

| Check | Result | Notes |
|-------|--------|-------|
| `pytest` (23 tests) | 23 PASSED, 0 FAILED | `testing/tests/unit/test_otel_pipeline.py` |
| `mypy --strict` | PASS (0 errors) | `testing/tests/unit/test_otel_pipeline.py` |
| `ruff check` | WARN (2 F541 violations) | Lines 52-53: f-strings without placeholders. Auto-fixable with `--fix`. |
| `@pytest.mark.requirement()` | 23/23 tests have markers | Full traceability. |
| No `pytest.skip()` | Confirmed: 0 occurrences | |
| No `time.sleep()` | Confirmed: 0 occurrences | |

## NF-7 Ruff Violation Detail

Two F541 violations in `testing/tests/unit/test_otel_pipeline.py:52-53`:
```python
f"configmap-otel.yaml must contain 'app.kubernetes.io/component: otel'. "
f"This is the source-of-truth label that E2E tests must match."
```
These are f-strings without any placeholders. Fix: remove the `f` prefix. Auto-fixable with `ruff check --fix`.

## Verdict

**APPROVED** -- All 5 acceptance criteria have direct implementation evidence with matching file:line references and structural unit tests that pass. The 2 ruff F541 lint violations are cosmetic (f-string prefix without placeholders) and auto-fixable; they do not affect correctness or behavior.
