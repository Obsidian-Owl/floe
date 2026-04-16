# Research Context — Audit Structural Fixes

baselineCommit: e1dbdb3f64b2fec5574b3c006645173418fc5800

## Problem Statement

After 20+ E2E-related work units shipped since February 2026, tests still fail
unpredictably. The audit (AUDIT.md) identified 4 structural root causes — not
random bugs but reinforcing design gaps. The user directed: "Our manifests should
be configuring everything. No hardcoding. And optimise processing to run at the
right time, in the right order. Not 8 times when it could be 1 time."

## Research Findings

### 1. Plugin Lifecycle Gap (ARC-001)

**Call sequence**: Discovery → Loading (`config=None`) → Configure (push via `_config`) → Connect

- `loader.py:160-176` — instantiates plugins with `plugin_class(config=None)` fallback
- `plugin_registry.py:330-334` — pushes config via `plugin._config = validated_config` (reflection)
- `plugin_metadata.py:76-256` — ABC has NO `configure()` method, no state tracking
- The gap IS closed by `create_iceberg_resources()` calling `registry.configure()` before `connect()`,
  but the pattern is fragile: no ABC contract, no state machine, any consumer that calls `connect()`
  before `configure()` gets garbage

**Key files**:
- `packages/floe-core/src/floe_core/plugin_metadata.py:76-256` — ABC definition
- `packages/floe-core/src/floe_core/plugins/loader.py:160-176` — loading with config=None
- `packages/floe-core/src/floe_core/plugin_registry.py:273-342` — configure() method
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` — requires config in __init__
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py` — consumer

### 2. Config Source of Truth Divergence (ARC-002)

**Divergences found**:

| Config | manifest.yaml | test-e2e.sh | Status |
|--------|--------------|-------------|--------|
| Bucket | `floe-data` | `floe-iceberg` (line 388) | DIVERGED |
| Warehouse | `floe-e2e` | `floe-e2e` (line 416) | Fixed (ebbfa27) |
| OAuth scope | `PRINCIPAL_ROLE:ALL` | NOT passed | DIVERGED |
| S3 region | `us-east-1` | Hardcoded `us-east-1` | Redundant |
| path_style_access | `true` | Hardcoded `true` | Redundant |

**Hardcoded values in test-e2e.sh** (lines 455-489):
- `MINIO_ENDPOINT = 'http://floe-platform-minio:9000'` — K8s internal, correct for catalog creation
- `s3.region: 'us-east-1'` — should read from manifest storage.config.region
- `s3.path-style-access: 'true'` — should read from manifest storage.config.path_style_access

**Hardcoded values in conftest.py**:
- `POLARIS_CREDENTIAL=demo-admin:demo-secret` — should derive from manifest
- `scope=PRINCIPAL_ROLE:ALL` — should derive from manifest

**Legitimate divergences** (NOT config drift):
- S3 endpoint: `http://floe-platform-minio:9000` vs `http://localhost:9000` — K8s vs port-forward
- Polaris URI: K8s DNS vs `localhost:8181` — same split, different access path

**Key files**:
- `demo/manifest.yaml` — source of truth
- `testing/ci/test-e2e.sh:380-510` — infrastructure setup with hardcoded values
- `tests/e2e/conftest.py` — fixture config with hardcoded defaults

### 3. E2E Test dbt Redundancy (E2E-002)

**dbt invocations in test_data_pipeline.py**:
- 7 `dbt seed` calls + 8 `dbt run` calls across independent test methods
- Each test independently seeds+runs as setup
- With 3-product parametrization: ~24 full dbt cycles when 3-4 suffice
- Each cycle: 50-95 seconds (seed) + 60-120 seconds (run)

**Test classification of e2e/ directory (non-E2E tests)**:
- `test_profile_isolation.py` — 17 tests, UNIT tier (no K8s needed)
- `test_dbt_e2e_profile.py` — 21 tests, UNIT tier (no K8s needed)
- `test_plugin_system.py` — 10 tests, UNIT tier (no K8s needed)
- Total: ~48 tests running in E2E that don't need K8s (~15-20 min wasted)

**State mutation analysis**: Most tests in test_data_pipeline.py read from
identical tables after the same seed+run cycle. Module-scoped fixtures would
reduce ~24 cycles to ~3 (one per product).

**Key files**:
- `tests/e2e/test_data_pipeline.py` — main redundancy source
- `tests/e2e/test_profile_isolation.py` — should move to unit
- `tests/e2e/test_dbt_e2e_profile.py` — should move to unit
- `tests/e2e/test_plugin_system.py` — should move to unit
- `tests/e2e/dbt_utils.py` — dbt subprocess helper

### 4. Fail-Fast on Startup (ARC-004)

**Location**: `floe_orchestrator_dagster/resources/iceberg.py:187-197`

`try_create_iceberg_resources()` catches ALL exceptions and returns `{}`.
Dagster starts, health checks pass, first sign of trouble is when an asset run
fails with "resource 'iceberg' not found" — minutes to hours after the actual
root cause.

**Key files**:
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:187-197`
