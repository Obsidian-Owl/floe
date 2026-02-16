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

## WU-11: Demo Packaging (Production-Like Workflow)

**Design**: [wu-11-design.md](./wu-11-design.md)

### AC-11.1: Dockerfile builds and contains demo code at importable paths

**How we know it works**: `docker build -f docker/dagster-demo/Dockerfile .` succeeds.

- Dockerfile extends `dagster/dagster-celery-k8s:1.9.6` base image
- Demo code COPY'd with underscore directory names: `customer_360/`, `iot_telemetry/`, `financial_risk/`
- Each product directory has `__init__.py` for Python package discovery
- `manifest.yaml` and `macros/` copied to `/app/demo/`
- `pip check` passes inside image (no broken dependency metadata)
- Shared macros at `/app/demo/macros/` accessible via `../macros` from each product dir

### AC-11.2: dbt compile produces target/manifest.json for each product

**How we know it works**: Makefile `compile-demo` target runs `dbt compile` for all 3 products.

- `demo/customer-360/target/manifest.json` exists after `make compile-demo`
- `demo/iot-telemetry/target/manifest.json` exists
- `demo/financial-risk/target/manifest.json` exists
- These files are present in the Docker build context (not gitignored from the build)

### AC-11.3: Helm values override Dagster image for webserver and daemon

**How we know it works**: Both `values-test.yaml` and `values-demo.yaml` set custom image.

- `dagster.dagsterWebserver.image.repository` == `floe-dagster-demo`
- `dagster.dagsterDaemon.image.repository` == `floe-dagster-demo`
- `dagster.dagsterWebserver.image.pullPolicy` == `Never` (Kind-loaded)
- Production `values.yaml` is NOT changed (still uses stock Dagster image)

### AC-11.4: Dagster pods start with custom image, code locations discoverable

**How we know it works**: After `make demo`, Dagster webserver discovers all 3 code locations.

- Dagster webserver pod runs `floe-dagster-demo:latest` image
- No `ModuleNotFoundError` in webserver logs
- All 3 code locations appear in Dagster UI workspace (K8s verification)

### AC-11.5: Module imports resolve correctly inside container

**How we know it works**: Module path configuration is correct.

- `moduleName: customer_360.definitions` with `workingDirectory: /app/demo`
- Dagster adds `/app/demo` to `sys.path` → `customer_360/definitions.py` found at `/app/demo/customer_360/definitions.py`
- Same for `iot_telemetry.definitions` and `financial_risk.definitions`
- `defs` attribute is importable from each module

### AC-11.6: Makefile chain works end-to-end

**How we know it works**: `make demo` runs the full production-like flow.

- `compile-demo` → `build-demo-image` → `demo` dependency chain
- `make compile-demo` runs `dbt compile` for each product
- `make build-demo-image` builds Docker image and loads to Kind
- `make demo` deploys via Helm upgrade

### AC-11.7: .dockerignore limits build context

**How we know it works**: `.dockerignore` exists at repo root.

- Excludes `.git/`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.specwright/`, `.beads/`, `.claude/`
- Docker build context is manageable size

### AC-11.8: Generated definitions.py produces functionally equivalent Dagster definitions

**How we know it works**: `floe platform compile --generate-definitions` output replaces hand-written files.

- Generated `definitions.py` written to each product directory
- Generated code exports `defs` attribute with Dagster Definitions
- Generated code uses `@dbt_assets` decorator with `DbtCliResource`
- Dagster webserver starts and discovers code locations with generated code

### AC-11.9: dbt relative paths resolve correctly inside container

**How we know it works**: `macro-paths: ["../macros"]` in each `dbt_project.yml` resolves.

- From `/app/demo/customer_360/`, `../macros` → `/app/demo/macros/` (exists in image)
- `profiles.yml` references are relative to project dir (DuckDB path: `target/demo.duckdb`)

### Boundary Conditions (WU-11)

- BC-11.1: Dockerfile builds on local architecture (amd64 or arm64 via Rosetta)
- BC-11.2: Demo code changes only require image rebuild, not Helm chart changes
- BC-11.3: Empty `target/` directory (no prior dbt compile) → `compile-demo` creates it
- BC-11.4: `pip install --no-deps` with `pip check` catches missing transitive deps
