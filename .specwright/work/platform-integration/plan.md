# Platform Integration — Implementation Plan

**Work ID**: platform-integration
**Date**: 2026-02-15
**Spec**: [spec.md](./spec.md)
**Design**: [design.md](./design.md)

---

## Work Unit Cycle

```
WU-9:  Config Pipeline Flow → /sw-build → /sw-verify → /sw-ship
WU-10: Polaris + Test Fixes → /sw-build → /sw-verify → /sw-ship
WU-11: Demo Packaging       → /sw-build → /sw-verify → /sw-ship
```

WU-9 is the critical path. WU-10 and WU-11 have no dependencies on WU-9 or each other.

---

## WU-9: Config Pipeline Flow

**Branch**: `feat/wu-9-config-pipeline-flow`
**Estimated tasks**: 7

### Task T49: Add ObservabilityManifestConfig to PlatformManifest schema

**Files**:
- `packages/floe-core/src/floe_core/schemas/manifest.py` — Add `TracingManifestConfig`, `LineageManifestConfig`, `LoggingManifestConfig`, `ObservabilityManifestConfig` models. Add `observability` field to `PlatformManifest`. Update `warn_on_extra_fields` validator to exclude `observability`.

**ACs**: AC-9.1
**Tests**: Unit tests in `packages/floe-core/tests/unit/schemas/test_manifest.py` — validate demo manifest loads with typed observability, test default values, test empty observability, update unknown-field warning tests.

### Task T50: Add lineage fields to ObservabilityConfig + version bump

**Files**:
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` — Add `lineage_endpoint: str | None` and `lineage_transport: Literal["http", "console", "noop"] | None` to `ObservabilityConfig`.
- `packages/floe-core/src/floe_core/schemas/versions.py` — Bump `COMPILED_ARTIFACTS_VERSION` to `"0.8.0"`, add history entry.

**ACs**: AC-9.2, AC-9.3
**Tests**: Contract tests in `tests/contract/test_compilation.py` — validate new fields serialize/deserialize, backwards compat (None defaults), version assertion updated.

### Task T51: Wire governance from manifest to CompiledArtifacts

**Files**:
- `packages/floe-core/src/floe_core/compilation/stages.py` — After loading manifest, convert `manifest.governance` (GovernanceConfig) → `ResolvedGovernance`. Pass to `build_artifacts()`.
- `packages/floe-core/src/floe_core/compilation/builder.py` — Add `governance: ResolvedGovernance | None = None` parameter to `build_artifacts()`. Pass to `CompiledArtifacts()`.

**ACs**: AC-9.4, AC-9.7
**Tests**: Unit tests in `packages/floe-core/tests/unit/compilation/test_stages.py` — compile with demo manifest → governance populated. Compile without governance → None.

### Task T52: Implement enforcement level precedence rule

**Files**:
- `packages/floe-core/src/floe_core/compilation/stages.py` — Replace `getattr(spec, "governance", None)` logic with "stricter wins" merge of manifest and spec governance levels.

**ACs**: AC-9.5
**Tests**: Unit tests — 4 parametrized cases: manifest-only, spec-strengthens, manifest-wins, both-None.

### Task T53: Builder reads manifest.observability

**Files**:
- `packages/floe-core/src/floe_core/compilation/builder.py` — Replace hardcoded `ObservabilityConfig` with manifest-sourced values. Read `manifest.observability` for endpoints, enabled flags.

**ACs**: AC-9.6
**Tests**: Unit tests — compile with demo manifest → observability has OTel endpoint from manifest. Compile without observability → defaults.

### Task T54: Contract test updates for version 0.8.0

**Files**:
- `tests/contract/test_compilation.py` — Update version assertions from 0.7.0 to 0.8.0. Add tests for lineage_endpoint in serialized output. Verify backwards compat.

**ACs**: AC-9.2, AC-9.3 (contract verification)
**Tests**: Contract tests that serialize → deserialize CompiledArtifacts with new fields.

### Task T55: Boundary condition tests

**Files**:
- `packages/floe-core/tests/unit/schemas/test_manifest.py` — BC-9.1, BC-9.2 (empty/partial observability)
- `packages/floe-core/tests/unit/compilation/test_stages.py` — BC-9.3, BC-9.4 (governance edge cases)

**ACs**: BC-9.1 through BC-9.4

### File Change Map (WU-9)

| File | Change Type | Tasks |
|------|-------------|-------|
| `packages/floe-core/src/floe_core/schemas/manifest.py` | ADD models + field | T49 |
| `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` | EDIT ObservabilityConfig | T50 |
| `packages/floe-core/src/floe_core/schemas/versions.py` | EDIT version + history | T50 |
| `packages/floe-core/src/floe_core/compilation/stages.py` | EDIT governance logic | T51, T52 |
| `packages/floe-core/src/floe_core/compilation/builder.py` | EDIT signature + body | T51, T53 |
| `packages/floe-core/tests/unit/schemas/test_manifest.py` | EDIT + ADD tests | T49, T55 |
| `packages/floe-core/tests/unit/compilation/test_stages.py` | ADD tests | T51, T52, T55 |
| `tests/contract/test_compilation.py` | EDIT version + ADD tests | T54 |

---

## WU-10: Polaris + Test Fixes

**Branch**: `feat/wu-10-polaris-test-fixes`
**Estimated tasks**: 5

### Task T56: Pin Polaris to 1.2.1-incubating

**Files**:
- `charts/floe-platform/values-test.yaml` — Change `polaris.image.tag` from `"1.3.0-incubating"` to `"1.2.1-incubating"`.

**ACs**: AC-10.1

### Task T57: Remove stale xfail markers

**Files**:
- `tests/e2e/test_*.py` — Find and remove `@pytest.mark.xfail(strict=True)` markers on tests that now reliably pass.

**ACs**: AC-10.2
**Tests**: Run affected tests 3 times to confirm no flakiness.

### Task T58: Fix STORAGE plugin test + health check mock + secrets

**Files**:
- `tests/e2e/test_plugin_system.py` — Fix STORAGE plugin assertion to validate manifest config, not entry point registry.
- `tests/e2e/test_*.py` or `tests/unit/test_*.py` — Fix MagicMock comparison in health check test.
- `devtools/` or `pyproject.toml` — Bump affected package or add pragma for secrets detection.

**ACs**: AC-10.3, AC-10.4, AC-10.5

### Task T59: Fix dbt profile generation for in-cluster

**Files**:
- `packages/floe-core/src/floe_core/compilation/` or `plugins/floe-compute-duckdb/` — Verify dbt profiles.yml DuckDB path is writable. May need to set DuckDB database path to a writable temp directory.

**ACs**: AC-10.6

### Task T60: Infrastructure bootstrap timing fix

**Files**:
- `charts/floe-platform/values-test.yaml` or `testing/ci/` scripts — Add readiness wait for MinIO bucket creation before E2E test execution.

**ACs**: AC-10.7

### File Change Map (WU-10)

| File | Change Type | Tasks |
|------|-------------|-------|
| `charts/floe-platform/values-test.yaml` | EDIT Polaris tag | T56 |
| `tests/e2e/test_*.py` | EDIT remove xfail + fix assertions | T57, T58 |
| `tests/e2e/test_plugin_system.py` | EDIT STORAGE assertion | T58 |
| `plugins/floe-compute-duckdb/` | EDIT dbt profile path | T59 |
| `testing/ci/` or Makefile | EDIT bootstrap wait | T60 |

---

## WU-11: Demo Packaging (Production-Like Workflow)

**Branch**: `feat/wu-11-demo-packaging`
**Design**: [wu-11-design.md](./wu-11-design.md)
**Estimated tasks**: 5

### Task T61: Create Dockerfile + .dockerignore

**Files**:
- `docker/dagster-demo/Dockerfile` — NEW. Extends `dagster/dagster-celery-k8s:1.9.6`. Installs floe packages (`--no-deps` + `pip check`). COPY demo code with hyphen→underscore rename. Adds `__init__.py` per product.
- `.dockerignore` — NEW. Excludes `.git/`, `.venv/`, caches, `.specwright/`, `.beads/`, `.claude/`.

**ACs**: AC-11.1, AC-11.7
**Tests**: Unit test (T64) validates Dockerfile structure and .dockerignore content.

### Task T62: Add Makefile targets (compile-demo, build-demo-image)

**Files**:
- `Makefile` — ADD `compile-demo` target (runs `dbt compile` for each product). ADD `build-demo-image` target (depends on `compile-demo`, runs `docker build` + `kind load`). UPDATE `demo` target to depend on `build-demo-image`.

**ACs**: AC-11.2, AC-11.6
**Note**: `compile-demo` must run before `docker build` so `target/manifest.json` is in the build context. The `@dbt_assets` decorator reads this at import time.

### Task T63: Update Helm values for image override + module paths

**Files**:
- `charts/floe-platform/values-test.yaml` — EDIT: Add `dagster.dagsterWebserver.image` and `dagster.dagsterDaemon.image` overrides. Change `moduleName` from `demo.customer_360.definitions` to `customer_360.definitions`. Change `workingDirectory` from `/app/demo` to `/app/demo` (keep as-is for sys.path).
- `charts/floe-platform/values-demo.yaml` — EDIT: Same image override and module path changes.

**ACs**: AC-11.3, AC-11.5
**Key detail**: `workingDirectory: /app/demo` adds `/app/demo` to sys.path. `moduleName: customer_360.definitions` resolves to `/app/demo/customer_360/definitions.py`. Both webserver and daemon use the same image.

### Task T64: Add structural validation unit tests

**Files**:
- `testing/tests/unit/test_demo_packaging.py` — NEW. Structural validation tests (YAML parsing, no K8s required):
  - Dockerfile exists at `docker/dagster-demo/Dockerfile` and has correct FROM instruction
  - Dockerfile COPYs all 3 products with underscore names
  - Dockerfile creates `__init__.py` for each product
  - `.dockerignore` exists and excludes key directories
  - `values-test.yaml` has Dagster image override with `pullPolicy: Never`
  - `values-demo.yaml` has Dagster image override
  - Module names use underscores (not hyphens), no `demo.` prefix
  - `workingDirectory` is `/app/demo` (not per-product)
  - Shared macros COPY'd to `/app/demo/macros/`
  - Each dbt_project.yml `macro-paths: ["../macros"]` — validates relative path works with directory layout

**ACs**: AC-11.1, AC-11.3, AC-11.5, AC-11.7, AC-11.9
**Pattern**: Same as `test_ci_workflows.py` — YAML parsing tests, no external services.

### Task T65: Validate generated definitions.py (Phase 2)

**Files**:
- `Makefile` — EDIT: Add `--generate-definitions` flag to `compile-demo` target.
- `demo/customer-360/definitions.py` — REPLACED by generated output
- `demo/iot-telemetry/definitions.py` — REPLACED by generated output
- `demo/financial-risk/definitions.py` — REPLACED by generated output
- `testing/tests/unit/test_demo_packaging.py` — ADD: Test that generated `definitions.py` exports `defs` attribute.

**ACs**: AC-11.8
**Verification**: Generated `definitions.py` must export `defs` (a `Definitions` object) with `@dbt_assets` and `DbtCliResource`. Functional equivalence, not source code identity.
**Depends on**: T61-T64 (packaging infrastructure must work first).

### File Change Map (WU-11)

| File | Change Type | Tasks |
|------|-------------|-------|
| `docker/dagster-demo/Dockerfile` | NEW | T61 |
| `.dockerignore` | NEW | T61 |
| `Makefile` | EDIT (add targets) | T62, T65 |
| `charts/floe-platform/values-test.yaml` | EDIT (image + modules) | T63 |
| `charts/floe-platform/values-demo.yaml` | EDIT (image + modules) | T63 |
| `testing/tests/unit/test_demo_packaging.py` | NEW | T64, T65 |
| `demo/*/definitions.py` | REPLACED (generated) | T65 |

---

## Architecture Decisions

### AD-1: Typed schema over model_extra for manifest observability
The `PlatformManifest` uses `extra="allow"` for forward compatibility. We add `observability` as a typed field (not read from `model_extra`) because typed fields provide validation, IDE autocomplete, and JSON Schema export. `resource_presets` stays in `model_extra` as follow-up.

### AD-2: MINOR version bump for lineage endpoint fields
Adding `lineage_endpoint` and `lineage_transport` to `ObservabilityConfig` is a MINOR change (new optional fields). Bump from 0.7.0 to 0.8.0 per project versioning rules.

### AD-3: "Stricter wins" governance precedence
Manifest governance is authoritative (platform team). Spec governance can only strengthen. This aligns with the `GovernanceConfig` inheritance rule and Constitution Principle VII (config flows DOWN only).

### AD-4: Pin Polaris over pyiceberg workaround
PyIceberg 0.11.0rc2 doesn't support PUT method. We pin Polaris 1.2.1 (known compatible) rather than monkey-patching pyiceberg internals. Filed as upstream issue.

### AD-5: Custom Dagster test image (not init container)
A Dockerfile extending the base image is explicit, reproducible, and cacheable. Init containers add startup latency and require volume management. The custom image is test-only.

---

## Verification Commands

```bash
# After WU-9:
uv run ruff check packages/floe-core/src/ && uv run ruff format --check packages/floe-core/src/
uv run pytest packages/floe-core/tests/unit/ -v --tb=short -x
uv run pytest tests/contract/test_compilation.py -v --tb=short -x

# After WU-10:
# (requires K8s cluster with Polaris 1.2.1 deployed)
make test-e2e

# After WU-11:
docker build -f testing/Dockerfile.dagster -t floe-dagster-test:latest .
make test-e2e
```
