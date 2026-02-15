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

## WU-11: Demo Packaging

**Branch**: `feat/wu-11-demo-packaging`
**Estimated tasks**: 3

### Task T61: Create testing/Dockerfile.dagster

**Files**:
- `testing/Dockerfile.dagster` — NEW file. Extends `dagster/dagster-celery-k8s` base image. `COPY demo/ /app/demo/`. `pip install` demo dependencies (floe-core, etc.).

**ACs**: AC-11.1

### Task T62: Override Dagster image in values-test.yaml

**Files**:
- `charts/floe-platform/values-test.yaml` — Add Dagster image override to use custom test image.
- `Makefile` or `testing/ci/` — Add build step for the custom Dagster image before E2E tests.

**ACs**: AC-11.2

### Task T63: Verify workspace module resolution

**Files**:
- No new files — verification via E2E test run.
- May need `demo/setup.py` or `demo/pyproject.toml` if demo modules need to be pip-installable.

**ACs**: AC-11.3, BC-11.1, BC-11.2

### File Change Map (WU-11)

| File | Change Type | Tasks |
|------|-------------|-------|
| `testing/Dockerfile.dagster` | NEW | T61 |
| `charts/floe-platform/values-test.yaml` | EDIT image override | T62 |
| `Makefile` | EDIT add build step | T62 |
| `demo/pyproject.toml` or `demo/setup.py` | NEW or EDIT | T63 |

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
