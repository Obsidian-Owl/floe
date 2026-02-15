# Platform Integration — Research Context

## Research Findings

### E2E Test Results (2026-02-15)
72 passed, 36 failed, 18 xfailed, 2 xpassed, 12 errors (34min runtime)

### Root Cause Categories

| # | Category | Count | Root Cause |
|---|----------|-------|------------|
| 1 | Dagster Code Locations | 3 fail | Demo Python modules not in container (`/app/demo/` missing) |
| 2 | xfail→xpass | 5 fail | `strict=True` on xfail markers — tests now pass but markers force failure |
| 3 | Governance Missing | 4 fail | `build_artifacts()` never passes `governance=` to CompiledArtifacts |
| 4 | Observability | 11 fail | OTel uses NoOpTracer (no exporter configured), lineage not emitted at compile time |
| 5 | Secrets/CVE | 2 fail | Test file pattern detection, devtools pip-audit vuln |
| 6 | Polaris 1.3.0 | 6 err + 5 fail | Polaris returns 'PUT' as endpoint method, auth on config endpoint |
| 7 | dbt Execution | 2 fail | dbt profiles misconfigured for in-cluster execution |
| 8 | Infrastructure Bootstrap | 4 fail | test-connection pod, MinIO bucket creation timing |
| 9 | Plugin Discovery | 1 fail | STORAGE PluginType not registered in entry points |
| 10 | Health Check Mock | 1 fail | MagicMock comparison in health check test |

### Key File Paths

#### Compilation Pipeline
- `packages/floe-core/src/floe_core/compilation/stages.py` — 6-stage pipeline with OTel spans
  - L223-229: Parent span `compile.pipeline`
  - L338-341: Governance reads from `spec.governance` (NOT manifest)
  - L393-403: Calls `build_artifacts()` without `governance=`
- `packages/floe-core/src/floe_core/compilation/builder.py` — Artifact builder
  - L43-54: Signature — no `governance` param
  - L110-125: ObservabilityConfig hardcoded, NOT from manifest
  - L127-139: CompiledArtifacts construction — no governance
- `packages/floe-core/src/floe_core/compilation/loader.py` — YAML loading
- `packages/floe-core/src/floe_core/compilation/resolver.py` — Plugin resolution

#### Schemas
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - L338-382: `ResolvedGovernance` — has pii_encryption, audit_logging, policy_enforcement_level, data_retention_days
  - L385-415: `ObservabilityConfig` — has telemetry (TelemetryConfig), lineage, lineage_namespace
  - L526-651: `CompiledArtifacts` — has `governance: ResolvedGovernance | None` (L649) and `observability` (existing)
- `packages/floe-core/src/floe_core/schemas/manifest.py`
  - L118-241: `GovernanceConfig` — full governance with policy_enforcement_level, naming, quality_gates, RBAC, etc.
  - L244-300: `PlatformManifest` — root model with `.governance` field

#### Telemetry
- `packages/floe-core/src/floe_core/telemetry/provider.py` — `TelemetryProvider` with OTLP exporter setup
- `packages/floe-core/src/floe_core/telemetry/config.py` — `TelemetryConfig` model
- `packages/floe-core/src/floe_core/telemetry/spans.py` — `create_span()` uses global tracer

#### Lineage
- `packages/floe-core/src/floe_core/lineage/emitter.py` — `LineageEmitter` with emit_start/complete/fail
- Lineage is emitted at RUNTIME by orchestrator plugins, NOT at compile time (by design)

#### Demo
- `demo/manifest.yaml` — Has observability.tracing.endpoint, governance.policy_enforcement_level, lineage config
- `demo/customer-360/floe.yaml` — References `../manifest.yaml`, has transforms, NO governance section
- `demo/customer-360/definitions.py` — Dagster definitions using dbt project
- `charts/floe-platform/templates/configmap-dagster-workspace.yaml` — workspace.yaml from values

#### Helm Charts
- `charts/floe-platform/charts/cube/` — Fixed in previous session (configmap, statefulset, deployment)
- `charts/floe-platform/values-test.yaml` — Test overrides for CI
- `charts/floe-platform/templates/` — Parent chart templates

### Gotchas

1. **`spec.governance` vs `manifest.governance`**: The demo floe.yaml has NO governance section. `getattr(spec, "governance", None)` returns None, so enforcement defaults to "warn". The manifest HAS governance with `policy_enforcement_level: warn`. These happen to match but only by coincidence.

2. **TelemetryProvider vs create_span()**: `create_span()` in spans.py uses the global OpenTelemetry tracer. Without calling `TelemetryProvider.initialize()` with an OTLP exporter, all spans go to NoOpTracer. The manifest has `observability.tracing.endpoint: http://floe-platform-otel:4317` but nothing reads it.

3. **ObservabilityConfig in builder.py**: Lines 110-125 hardcode `TelemetryConfig(enabled=True, ...)` with default `ResourceAttributes`. The manifest's `observability.tracing` section is never consulted. The `deployment_environment` is hardcoded to `"dev"`.

4. **Polaris 1.3.0 breaking change**: Returns 'PUT' as HTTP method for table config endpoint. PyIceberg's `ConfigResponse` model only accepts GET/POST/HEAD/DELETE. Need pyiceberg upgrade or workaround.

5. **Demo code not in container**: Standard Dagster image doesn't have demo code. Workspace configmap references `demo.customer_360.definitions` but module doesn't exist. Need either custom image or init container.

6. **OpenLineage at compile time**: The lineage emitter infrastructure exists but is correctly NOT called during compilation. Lineage events are emitted when the orchestrator actually runs transformations. E2E tests that check for lineage after compilation only will fail — need to run actual pipelines.

7. **STORAGE plugin type**: `PluginType.STORAGE` exists in the enum but no entry point is registered. The `s3` storage config in manifest is a config section, not a plugin that needs discovery. The E2E test incorrectly expects a registered storage plugin.
