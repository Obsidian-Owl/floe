# Context: E2E Permanent Fixes

baselineCommit: f1f1e25c00fe64845da9166b06c9b4654670bd8d

## Research Sources

- `.specwright/research/e2e-structural-resolution-20260405.md` — 4-track analysis with cited sources
- `.specwright/AUDIT.md` — architecture audit (ARC-001..004, E2E-001..004)

## Key File Paths

### Unit 1: Iceberg Table Purge
- `tests/e2e/dbt_utils.py:73-108` — `_purge_iceberg_namespace()` — uses `drop_table` (leaves S3 files)
- `tests/e2e/dbt_utils.py:25-70` — `_get_polaris_catalog()` with session cache
- PyIceberg `purge_table` IS available (`Catalog.purge_table` confirmed in 0.11.0rc2)
- Polaris bugs #1195, #1448 — server-side purge unreliable for metadata files
- MinIO S3 client needed for supplementary cleanup

### Unit 2: Polaris PostgreSQL Persistence  
- `charts/floe-platform/values-test.yaml:129-169` — Polaris config, NO persistence block
- `charts/floe-platform/values-test.yaml:201-204` — PostgreSQL enabled, persistence disabled
- `charts/floe-platform/templates/deployment-polaris.yaml` — deployment template
- `charts/floe-platform/templates/configmap-polaris.yaml` — Quarkus properties
- `charts/floe-platform/templates/job-polaris-bootstrap.yaml` — idempotent bootstrap

### Unit 3: Config Single Source of Truth
- `testing/ci/test-e2e.sh:458-486` — hardcodes `MINIO_ENDPOINT` and `table-default.*`
- `testing/ci/extract-manifest-config.py:43-60` — extracts manifest values
- `tests/e2e/conftest.py:54-60` — fallback `warehouse: "floe-e2e"` (diverges from manifest `floe-demo`)

### Unit 4: OpenLineage Facet Key + Template Lineage
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py:240` — `"parentRun"` key (should be `"parent"`)
- `plugins/floe-orchestrator-dagster/tests/unit/test_lineage_extraction.py:502-598` — unit tests assert `"parentRun"`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1344-1362` — template asset function (no lineage calls)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1160-1162` — lineage_resource wired but unused by asset fn
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:556-618` — dynamic path with full lineage emission

## Verified Facts
- `purge_table` exists in PyIceberg 0.11.0rc2 (verified via import)
- PostgreSQL is already deployed in test environment (`floe-platform-postgresql`)
- Polaris 1.2.0-incubating supports relational-jdbc persistence
- E2E test `test_observability.py:1085-1095` already checks both `"parentRun"` and `"parent"` keys (defensive)
- Template asset function signature: `def {safe_name}_dbt_assets(context, dbt: DbtCliResource)`
- Dynamic asset function takes additional `lineage: LineageResource` parameter

## Gotchas
- `table-default.s3.endpoint` in test-e2e.sh is CORRECT for in-cluster operation — K8s hostname resolves inside cluster
- Polaris PostgreSQL needs a database created (or Quarkus auto-creates schema)
- Template generation is in plugin.py:1317-1363 — changes affect all `floe compile --generate-definitions` outputs
- Existing unit tests for lineage_extraction assert `"parentRun"` — must update in sync with key change

## Pivot: Option B — Runtime Loader (2026-04-06)

### Reason
Analysis revealed 96% boilerplate in generated `definitions.py` files, module-load-time crashes, and divergence between dynamic and generated code paths. The original 4 fixes addressed symptoms; Option B addresses root causes.

### Key Architectural Finding: Two dbt Paths
- `create_definitions()` (plugin.py:183-287) → per-model `@asset` → `dbt.run_models(select=name)` — SDK path
- Generated `definitions.py` → single `@dbt_assets(manifest=...)` → `dbt.cli(["build"]).stream()` — workspace path
- The runtime loader replaces the generated path, NOT the SDK path

### Unit 5: Runtime Loader (NEW)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py` — runtime loader
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` — extracted Iceberg export
- `demo/customer-360/definitions.py` — simplified to ~15 lines
- `demo/iot-telemetry/definitions.py` — simplified
- `demo/financial-risk/definitions.py` — simplified
- `plugin.py` template section — simplified to emit thin loader

### Critic WARNs (implementation notes)
1. ResourceDefinition wrapper: fail-fast on error, never yield None
2. try/except around yield from dbt.cli().stream() for emit_fail
3. Lineage transport is partially eager — acceptable, document in comments
4. Pass parsed CompiledArtifacts to export function (not re-read file)

## Pivot: Expand to All Audit BLOCKERs (2026-04-06)

### Reason
DX audit revealed 6 BLOCKERs. Runtime-loader only addresses 2 (DX-001, DX-002). User rejected deferral of DX-004 and DBT-001: "Yes - they must be solved!!! These are critical issues!!!"

### New Units (6-9)
- **Unit 6: loud-failures** — Fix DX-003 (silent failure) and CON-001 (inconsistent try_create_*). Standardize all 4 resource factories to re-raise on configured-but-broken. Contract test as regression gate.
- **Unit 7: config-merge-fix** — Fix DX-004 (S3 endpoint corruption). Remove `table-default.s3.endpoint` from Polaris bootstrap. Add client endpoint override in catalog plugin. Contract + integration tests.
- **Unit 8: credential-consolidation** — Fix DBT-001 (credentials in 31 files). Centralized credentials module. All consumers read from manifest or env vars. Contract test scanning for hardcoded credentials.
- **Unit 9: e2e-proof** — No production code. E2E tests proving ALL fixes work: thin loader happy path, loud failure on Polaris down, S3 endpoint preservation, credential consistency, full regression.

### Dependencies
```
Unit 5 (runtime-loader) → Unit 6 (loud-failures) → Unit 9 (e2e-proof)
Unit 7 (config-merge-fix) → Unit 9 (e2e-proof)
Unit 8 (credential-consolidation) → Unit 9 (e2e-proof)
```
Units 7 and 8 are independent of units 5-6.
