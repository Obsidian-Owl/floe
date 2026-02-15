# Platform Integration — Specification

**Work ID**: platform-integration
**Date**: 2026-02-15
**Design**: [design.md](./design.md)
**Context**: [context.md](./context.md)

---

## Work Unit Decomposition

| Unit | Name | Description | Dependencies |
|------|------|-------------|-------------|
| WU-9 | Config Pipeline Flow | Schema changes + governance/observability flow through builder | None |
| WU-10 | Polaris + Test Fixes | Pin Polaris, xfail cleanup, test assertion fixes | None |
| WU-11 | Demo Packaging | Custom Dagster test image with demo code | None |

WU-9 is the critical path (core pipeline fix). WU-10 and WU-11 are independent.

---

## WU-9: Config Pipeline Flow

### AC-9.1: ObservabilityManifestConfig schema on PlatformManifest

**How we know it works**: Loading the demo `manifest.yaml` populates `manifest.observability` as a typed `ObservabilityManifestConfig` (not `model_extra`).

- `manifest.observability.tracing.endpoint` == `"http://floe-platform-otel:4317"`
- `manifest.observability.lineage.endpoint` == `"http://floe-platform-marquez:5000/api/v1/lineage"`
- `manifest.observability.logging.level` == `"INFO"`
- `"observability"` does NOT appear in `model_extra` keys
- `PlatformManifest` without `observability` still loads (field is Optional)
- Existing `warn_on_extra_fields` tests updated — `observability` no longer in unknown-field list

### AC-9.2: Lineage endpoint fields on ObservabilityConfig (CompiledArtifacts)

**How we know it works**: `ObservabilityConfig` accepts `lineage_endpoint` and `lineage_transport` as optional fields.

- `ObservabilityConfig(telemetry=..., lineage_namespace="x", lineage_endpoint="http://marquez:5000/api/v1/lineage", lineage_transport="http")` constructs without error
- `ObservabilityConfig(telemetry=..., lineage_namespace="x")` still constructs (fields default to None)
- Existing contract tests that serialize/deserialize `CompiledArtifacts` still pass (backwards compatible)

### AC-9.3: COMPILED_ARTIFACTS_VERSION bumped to 0.8.0

**How we know it works**: `versions.py` has `COMPILED_ARTIFACTS_VERSION = "0.8.0"` and version history entry.

- Contract tests that assert `artifacts.version` updated to `"0.8.0"`
- Version history has entry: `"0.8.0": "Add lineage_endpoint, lineage_transport to ObservabilityConfig"`

### AC-9.4: Governance flows from manifest to CompiledArtifacts

**How we know it works**: `compile_pipeline(spec_path, manifest_path)` produces `CompiledArtifacts` with populated `governance` field.

- `artifacts.governance is not None` when manifest has governance section
- `artifacts.governance.policy_enforcement_level == "warn"` (from demo manifest)
- `artifacts.governance.audit_logging == "enabled"` (from demo manifest)
- `artifacts.governance.data_retention_days == 1` (from demo manifest)
- `artifacts.governance is None` when manifest has NO governance section (backwards compat)

### AC-9.5: Enforcement level precedence — manifest authoritative, spec strengthens only

**How we know it works**: The enforcement level in `EnforcementResultSummary` follows the "stricter wins" rule.

- manifest=`warn`, spec=None → enforcement_level=`"warn"`
- manifest=`warn`, spec=`strict` → enforcement_level=`"strict"` (spec strengthens)
- manifest=`strict`, spec=`warn` → enforcement_level=`"strict"` (manifest wins, can't weaken)
- manifest=None, spec=None → enforcement_level=`"warn"` (default)

### AC-9.6: Builder reads manifest.observability instead of hardcoding

**How we know it works**: `compile_pipeline()` with demo manifest produces `ObservabilityConfig` with values from manifest YAML.

- `artifacts.observability.telemetry.otlp_endpoint == "http://floe-platform-otel:4317"` (from manifest)
- `artifacts.observability.lineage == True` (from manifest)
- `artifacts.observability.lineage_endpoint == "http://floe-platform-marquez:5000/api/v1/lineage"` (from manifest)
- `artifacts.observability.lineage_transport == "http"` (from manifest)
- `artifacts.observability.telemetry.resource_attributes.service_name == "customer-360"` (from spec)
- Without manifest observability section: uses defaults (`http://localhost:4317`, lineage=True, endpoint=None)

### AC-9.7: build_artifacts() accepts governance parameter

**How we know it works**: `build_artifacts()` signature includes `governance: ResolvedGovernance | None = None` and passes it through.

- Calling with `governance=ResolvedGovernance(policy_enforcement_level="strict")` → `artifacts.governance.policy_enforcement_level == "strict"`
- Calling without governance → `artifacts.governance is None`

### Boundary Conditions (WU-9)

- BC-9.1: Manifest with `observability: {}` (empty) → uses all defaults (tracing.enabled=True, etc.)
- BC-9.2: Manifest with `observability.tracing` only (no lineage/logging) → lineage/logging use defaults
- BC-9.3: Manifest with governance but NO policy_enforcement_level → defaults to None (field is Optional)
- BC-9.4: Spec with governance that tries to weaken manifest → manifest level preserved

---

## WU-10: Polaris + Test Fixes

### AC-10.1: Polaris pinned to 1.2.1-incubating

**How we know it works**: `values-test.yaml` has `polaris.image.tag: "1.2.1-incubating"`.

- Helm template renders with Polaris 1.2.1 image
- PyIceberg can connect to Polaris without PUT method errors

### AC-10.2: Stale xfail markers removed

**How we know it works**: Tests that were `xfail(strict=True)` but now pass have markers removed.

- `grep -r "xfail" tests/e2e/` shows no markers for tests that reliably pass
- Previously-xfail tests now pass as normal tests (not xpass)

### AC-10.3: STORAGE plugin test assertion corrected

**How we know it works**: E2E test validates storage config presence via `CompiledArtifacts.plugins.storage` instead of plugin registry lookup.

- Test no longer expects a registered STORAGE entry point
- Test validates `artifacts.plugins.storage is not None` or validates manifest storage config

### AC-10.4: Health check mock comparison fixed

**How we know it works**: Health check test passes without MagicMock comparison error.

### AC-10.5: Secrets/CVE cleanup

**How we know it works**: `pip-audit` and detect-secrets pass clean on affected files.

### AC-10.6: dbt profile configuration for in-cluster execution

**How we know it works**: Generated dbt profiles.yml works with DuckDB compute plugin inside K8s.

- Profile `target` matches compute plugin config
- DuckDB path is writable inside the container

### AC-10.7: Infrastructure bootstrap timing

**How we know it works**: MinIO bucket creation and test-connection pod complete before E2E tests start.

- Readiness check or increased timeout prevents race condition
- E2E tests that depend on MinIO pass reliably

### Boundary Conditions (WU-10)

- BC-10.1: Polaris 1.2.1 pod starts and passes readiness probe
- BC-10.2: xfail removal doesn't introduce flaky failures (verify 3 consecutive runs)

---

## WU-11: Demo Packaging

### AC-11.1: Custom Dagster test image with demo code

**How we know it works**: `testing/Dockerfile.dagster` builds successfully, extends base Dagster image with demo code.

- `docker build -f testing/Dockerfile.dagster .` succeeds
- `/app/demo/customer_360/definitions.py` exists in image
- `/app/demo/iot_telemetry/definitions.py` exists in image
- `/app/demo/financial_risk/definitions.py` exists in image

### AC-11.2: values-test.yaml overrides Dagster image

**How we know it works**: `values-test.yaml` sets the Dagster image to the custom test image.

- Dagster webserver pod runs custom image (not stock `dagster-celery-k8s`)
- Dagster daemon pod runs custom image
- Production `values.yaml` is NOT changed (still uses stock image)

### AC-11.3: Workspace module references resolve

**How we know it works**: Dagster pods can import demo modules.

- `demo.customer_360.definitions` resolves inside the Dagster container
- `demo.iot_telemetry.definitions` resolves
- `demo.financial_risk.definitions` resolves
- Dagster webserver starts without code location errors

### Boundary Conditions (WU-11)

- BC-11.1: Image builds on both amd64 and arm64 (multi-arch or Rosetta)
- BC-11.2: Demo code changes don't require Helm chart changes (just image rebuild)
