# W3 Observability And Quality E2E Design

## Objective

Add focused Alpha E2E assertions proving the Customer 360 demo emits and exposes
real observability and quality evidence:

- OpenLineage events arrive in Marquez with Customer 360 identities.
- OpenTelemetry traces arrive in Jaeger with Customer 360 service/span evidence.
- Great Expectations validates real Customer 360 data materialized in Iceberg.

The work is test-led. Small production-code fixes are allowed only when stronger
E2E assertions prove missing wiring in the exercised path.

## Scope

W3 belongs in the normal local `make test-e2e` lane. The assertions should reuse
existing E2E fixtures and avoid becoming a second remote release-validation
suite.

In scope:

- Tighten lineage evidence to fresh Customer 360 runs where current tests rely on
  weaker or synthetic checks.
- Tighten telemetry evidence to traces created inside a bounded test window.
- Add the missing GX real-data path against Customer 360 Iceberg tables.
- Add focused production wiring fixes if the E2E path cannot truthfully pass.

Out of scope:

- Custom lineage facet validation.
- Trace sampling, performance, or retention validation.
- Quality alerting integration.
- Broad observability or plugin-system refactors.
- Moving W3 exclusively to DevPod/Hetzner remote validation.

## Existing Context

The repository already has stronger observability coverage than the starting
prompt implies:

- `tests/e2e/test_lineage_roundtrip_e2e.py` includes fresh Marquez run checks for
  runtime lineage.
- `tests/e2e/test_observability.py` includes Marquez graph, emission-point, and
  trace content assertions.
- `tests/e2e/test_observability_roundtrip_e2e.py` validates compile-time traces
  flowing through the OTel Collector into Jaeger.
- `tests/e2e/test_data_pipeline.py` runs dbt quality checks through
  `dbt test`.

The remaining Alpha gap is Great Expectations against real Iceberg data. The
main telemetry risk is accepting stale seeded traces instead of evidence created
by the current test run.

## Components

### E2E Tests

Prefer a new focused file, `tests/e2e/test_quality_gx_e2e.py`, for GX real-data
validation. This keeps plugin-level GX evidence separate from dbt pipeline
quality checks in `tests/e2e/test_data_pipeline.py`.

Tighten existing observability tests in place when possible:

- `tests/e2e/test_observability.py`
- `tests/e2e/test_observability_roundtrip_e2e.py`
- `tests/e2e/test_lineage_roundtrip_e2e.py`

Avoid adding duplicate observability modules unless the existing files cannot be
cleanly extended.

### Fixtures

Reuse existing fixtures before adding new ones:

- `compiled_artifacts`
- `dbt_pipeline_result`
- `polaris_client`
- `marquez_client`
- `jaeger_client`
- `trigger_lineage_run`
- `wait_for_condition`

Add helper functions only when they remove duplicated polling, parsing, or
freshness logic.

### Production Code

Production edits are permitted only when an E2E assertion proves a missing
integration point. Likely allowed areas:

- `plugins/floe-quality-gx/src/floe_quality_gx/`
- telemetry exporter initialization or service-name wiring
- lineage event emission or identity propagation

Do not add test-specific demo assumptions to production code.

## Data Flow

1. Compile `demo/customer-360/floe.yaml` with the real demo manifest.
2. Derive expected product, namespace, service, model, and table identities from
   `CompiledArtifacts` or existing demo fixture conventions.
3. Trigger or reuse a fresh Customer 360 execution through existing E2E fixtures.
4. Query external systems for concrete evidence:
   - Marquez for fresh OpenLineage jobs, runs, events, and datasets.
   - Jaeger for traces in the test time window.
   - Polaris/Iceberg for materialized Customer 360 tables.
5. Run `GreatExpectationsPlugin.run_suite()` against a DataFrame loaded from a
   real Iceberg table.
6. Assert names, states, span operations, attributes, check results, and record
   counts.

This preserves ownership boundaries: dbt owns SQL compilation, Iceberg owns
table storage, Marquez and Jaeger own observability backends, and GX owns
quality validation.

## Lineage Requirements

Lineage E2E evidence must be tied to the current Customer 360 run.

Assertions should verify:

- artifact-derived lineage namespace and product job name are present;
- a fresh Marquez run appears after the test snapshot;
- the fresh run reaches `COMPLETED`;
- expected model or dataset names are present when the test targets graph
  completeness;
- synthetic Marquez POSTs do not count as Alpha runtime evidence.

Existing synthetic Marquez API tests can remain as backend smoke coverage, but
they must not be the only proof for W3.

## Telemetry Requirements

Telemetry E2E evidence must be fresh or bounded by a timestamp captured around
the compile or execution action.

Assertions should verify:

- Jaeger returns traces for `customer-360`;
- traces were created in the test's bounded time window;
- spans have non-empty operation names;
- spans include useful Floe/domain attributes such as `compile.*`,
  `governance.*`, `enforcement.*`, or `floe.*`;
- parent-child span relationships are asserted where the tested path should
  create nested spans.

Seeded traces from previous runs should not satisfy W3 by themselves.

## Quality GX Requirements

The GX test should prove the plugin validates real Customer 360 data that was
materialized into Iceberg.

Recommended flow:

1. Use `dbt_pipeline_result` parametrized for `customer-360` to run seed and
   model materialization.
2. Load a stable Customer 360 table through `polaris_client`.
3. Convert the table scan to a pandas DataFrame.
4. Build a concrete `QualitySuite` with checks such as:
   - `customer_id` not null;
   - `customer_id` unique on a dimension table;
   - row count between expected bounds;
   - a known categorical/status column values in an expected set, if available.
5. Execute `GreatExpectationsPlugin.run_suite()` against the loaded data.
6. Assert:
   - suite name and model name;
   - all checks passed;
   - expected check names are present;
   - summary total, passed, and failed counts;
   - records were checked for column-level validations.

If the current plugin can only load DuckDB tables through connection config, the
E2E may pass the Iceberg-loaded DataFrame into the existing validation executor
directly, or production code may be minimally extended to support an explicit
DataFrame/Arrow handoff. Prefer the smallest truthful integration surface.

## Error Handling

W3 tests should fail loudly. Do not skip required Alpha evidence.

Failure messages should distinguish:

- infrastructure unavailable: Jaeger, Marquez, Polaris, MinIO, OTel Collector,
  or Dagster cannot be reached;
- no fresh evidence: the backend is reachable, but the current test run produced
  no new trace, lineage, or quality result;
- wrong evidence: data exists, but names, states, attributes, or validation
  results do not match Customer 360 expectations;
- plugin wiring failure: GX, telemetry, or lineage plugin cannot run against the
  real E2E data path.

Use bounded polling for Jaeger and Marquez. GX validation is synchronous once
the Iceberg data is loaded and should fail directly.

## Verification Plan

Implementation should proceed test-first:

1. Add the W3 E2E assertions.
2. Run focused GX E2E validation:
   `pytest tests/e2e/test_quality_gx_e2e.py -m e2e`
3. Run targeted observability tests if they are changed.
4. Apply minimal production wiring fixes only for failures proven by the tests.
5. Add focused unit or contract coverage for any touched production code.
6. Run lint/type checks for touched Python files.
7. Run the normal local E2E lane when practical:
   `make test-e2e`

## Acceptance Criteria

- Lineage evidence is fresh and tied to Customer 360 artifact-derived identities.
- Jaeger evidence is fresh or time-windowed and tied to `customer-360`.
- GX validates real Iceberg-backed Customer 360 data with concrete result
  assertions.
- No mocks are used in the E2E path.
- Existing E2E cleanup semantics remain intact.
- Production changes, if any, are limited to wiring required by the new E2E
  assertions.
