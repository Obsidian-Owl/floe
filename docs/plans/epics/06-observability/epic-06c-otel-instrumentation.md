# Epic 6C: OTel Code Instrumentation

## Summary

Adds OpenTelemetry span instrumentation to all floe platform layers, enabling distributed tracing across compilation, orchestration, and transformation. This epic builds on Epic 6A (OTel SDK setup) to add actual span emission at key operations so that pipelines are observable end-to-end.

**Key Insight**: Data products (demo/*, user pipelines) should NOT require manual OTel instrumentation. Tracing flows automatically through platform layers when properly instrumented.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [Epic 6C: OTel Code Instrumentation](https://linear.app/obsidianowl/project/epic-6c-otel-code-instrumentation-390eeee4c4ac)

---

## Requirements Covered

| Requirement ID | Description | Priority | E2E Test |
|----------------|-------------|----------|----------|
| FR-041 | Traces visible in Jaeger | CRITICAL | `test_traces_visible_in_jaeger` |
| FR-046 | Compilation emits OTel spans | CRITICAL | `test_compilation_emits_otel_spans` |
| FR-047 | All products show traces in Jaeger | HIGH | `test_jaeger_traces_for_all_products` |
| REQ-502 | Span creation for key operations | HIGH | (from 6A) |
| REQ-511 | Custom span attributes | HIGH | (from 6A) |
| REQ-512 | Error tracking | HIGH | (from 6A) |

---

## Architecture Alignment

### Target State (from Architecture Summary)

- **OpenTelemetry is ENFORCED** (not pluggable) - floe emits OTel traces to any backend
- **TelemetryBackendPlugin** handles OTLP export configuration (Jaeger, Datadog, etc.)
- Platform layers emit spans; data products inherit tracing automatically

### Layer Instrumentation Model

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: DATA (Data Products)                               │
│   demo/customer-360, demo/iot-telemetry, etc.               │
│   ➜ NO manual instrumentation needed                        │
│   ➜ Inherits traces from platform layers                    │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ (automatic propagation)
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: SERVICES (Orchestration)                           │
│   floe-orchestrator-dagster                                 │
│   ➜ Spans on: asset materialization, sensor evaluation      │
│   ➜ Context propagation across runs                         │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: TRANSFORMATION                                     │
│   floe-dbt (dbt commands)                                   │
│   ➜ Spans on: dbt run, dbt test, dbt build                  │
│   ➜ Model-level span attributes                             │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: FOUNDATION (Compilation)                           │
│   floe-core/compilation/stages.py                           │
│   ➜ Spans on: compile_pipeline, stage1-6, validation        │
│   ➜ Attributes: spec_path, manifest_path, artifacts_version │
└─────────────────────────────────────────────────────────────┘
```

---

## File Ownership (Exclusive)

```text
# Layer 1: Compilation instrumentation
packages/floe-core/src/floe_core/
├── compilation/
│   └── stages.py              # Add tracer.start_as_current_span
├── telemetry/
│   ├── __init__.py            # get_tracer() factory
│   ├── tracing.py             # @traced decorator, span utilities
│   └── conventions.py         # Semantic conventions (floe.*)

# Layer 2: dbt instrumentation
packages/floe-dbt/src/floe_dbt/        # (if exists, else floe-core/dbt/)
├── runner.py                  # Wrap dbt commands with spans

# Layer 3: Orchestrator instrumentation
plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/
├── tracing.py                 # Dagster-specific span utilities
├── io_managers/
│   └── traced_io_manager.py   # IOManager with OTel spans
└── sensors/
    └── traced_sensor.py       # Sensors with span context

# Test fixtures
testing/fixtures/telemetry.py      # Assert span presence helpers
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 6A | OTel SDK setup and TelemetryProvider |
| Blocked By | Epic 4B | Orchestrator plugin interface |
| Blocked By | Epic 5A | dbt plugin interface |
| Blocks | Epic 6B | OpenLineage correlates with OTel traces |
| Blocks | Epic 9B | Helm charts must configure OTel Collector |

---

## User Stories (for SpecKit)

### US1: Compilation Pipeline Spans (P0)

**As a** platform operator
**I want** traces emitted during compilation
**So that** I can debug slow or failing compilations

**Acceptance Criteria**:
- [ ] `compile_pipeline()` creates root span `floe.compile`
- [ ] Each compilation stage creates child span (`floe.compile.stage1`, etc.)
- [ ] Span attributes include: `floe.spec_path`, `floe.manifest_path`, `floe.artifacts_version`
- [ ] Errors recorded as span exceptions with stack traces
- [ ] Spans visible in Jaeger when OTLP exporter configured

**Implementation**:
```python
# packages/floe-core/src/floe_core/compilation/stages.py
from opentelemetry import trace
from floe_core.telemetry import get_tracer

tracer = get_tracer("floe-core")

def compile_pipeline(spec_path: Path, manifest_path: Path) -> CompiledArtifacts:
    with tracer.start_as_current_span(
        "floe.compile",
        attributes={
            "floe.spec_path": str(spec_path),
            "floe.manifest_path": str(manifest_path),
        }
    ) as span:
        try:
            artifacts = _run_stages(spec_path, manifest_path)
            span.set_attribute("floe.artifacts_version", artifacts.version)
            return artifacts
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise
```

### US2: Dagster Asset Materialization Spans (P0)

**As a** platform operator
**I want** traces for Dagster asset operations
**So that** I can see pipeline execution in Jaeger

**Acceptance Criteria**:
- [ ] `@asset` decorated functions create spans automatically
- [ ] IOManager read/write operations create child spans
- [ ] Span attributes include: `dagster.asset_key`, `dagster.run_id`, `dagster.step_key`
- [ ] Context propagated across asset dependencies

**Implementation**:
```python
# plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/tracing.py
from functools import wraps
from opentelemetry import trace

def traced_asset(fn):
    """Decorator that wraps Dagster assets with OTel spans."""
    tracer = trace.get_tracer("floe-dagster")

    @wraps(fn)
    def wrapper(context, *args, **kwargs):
        with tracer.start_as_current_span(
            f"dagster.asset.{context.asset_key.to_user_string()}",
            attributes={
                "dagster.asset_key": str(context.asset_key),
                "dagster.run_id": context.run_id,
                "dagster.step_key": context.step_key,
            }
        ):
            return fn(context, *args, **kwargs)
    return wrapper
```

### US3: dbt Command Spans (P1)

**As a** platform operator
**I want** traces for dbt operations
**So that** I can see transform execution details

**Acceptance Criteria**:
- [ ] `dbt run`, `dbt test`, `dbt build` create parent spans
- [ ] Individual model executions create child spans
- [ ] Span attributes include: `dbt.command`, `dbt.target`, `dbt.model_name`
- [ ] dbt logs correlated with trace IDs

### US4: Automatic Propagation to Data Products (P2)

**As a** data engineer
**I want** my pipelines to be traced automatically
**So that** I don't need to add instrumentation code

**Acceptance Criteria**:
- [ ] Demo products show traces without any OTel code in definitions.py
- [ ] Trace context flows from CLI → compilation → orchestration → dbt
- [ ] User pipelines inherit tracing from platform

---

## Technical Notes

### Key Decisions

1. **Instrumentation is in platform layers, not data products** - Users don't write OTel code
2. **`@traced` decorator pattern** - Reusable instrumentation without boilerplate
3. **Semantic conventions use `floe.*` namespace** - Clear attribution in trace backends
4. **Error spans use `record_exception()`** - Full stack traces in Jaeger

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance overhead | LOW | MEDIUM | Sampling configuration per environment |
| Context loss across processes | MEDIUM | HIGH | W3C Trace Context propagation |
| Dagster integration complexity | MEDIUM | MEDIUM | Use Dagster's built-in OTel integration |

### Test Strategy

- **Unit**: `packages/floe-core/tests/unit/test_compilation_tracing.py`
- **Integration**: `tests/integration/test_otel_jaeger.py` (spans reach Jaeger)
- **E2E**: `tests/e2e/test_observability.py::test_traces_visible_in_jaeger`

---

## E2E Test Alignment

| Test | Current Status | After Epic |
|------|----------------|------------|
| `test_otel_collector_running` | FAIL (label mismatch) | Fixed by Epic 9B (Helm) |
| `test_traces_visible_in_jaeger` | FAIL (no spans) | PASS |
| `test_compilation_emits_otel_spans` | FAIL (no spans) | PASS |
| `test_jaeger_traces_for_all_products` | FAIL (no spans) | PASS |

---

## SpecKit Context

### Relevant Codebase Paths
- `packages/floe-core/src/floe_core/compilation/`
- `packages/floe-core/src/floe_core/telemetry/`
- `plugins/floe-orchestrator-dagster/`
- `tests/e2e/test_observability.py`

### Related Existing Code
- `floe_core/telemetry/config.py` - TelemetryConfig, ResourceAttributes
- `floe_core/schemas/compiled_artifacts.py` - ObservabilityConfig

### External Dependencies
- `opentelemetry-api>=1.20.0`
- `opentelemetry-sdk>=1.20.0`
- `opentelemetry-exporter-otlp>=1.20.0`
- `opentelemetry-instrumentation-dagster` (if available)
