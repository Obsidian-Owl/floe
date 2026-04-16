# Context: E2E Alpha Stability

Research findings and file references for downstream agents.

---

## Fix A: .vuln-ignore sync

- **File**: `.vuln-ignore` (root)
- **CVE**: `GHSA-gc5v-m9x4-r6x2` — requests `extract_zipped_paths()` vulnerability
- **Rationale in**: `pyproject.toml:233-238`
- **Blocker**: `datacontract-cli` pins `requests<2.33` through v0.11.7
- **Test**: `test_pip_audit_clean` reads `.vuln-ignore`, not `pyproject.toml`
- **Pattern**: P39 — single-file ignore lists

## Fix B: Demo profiles.yml

- **Files**:
  - `demo/customer-360/profiles.yml` — `path: "target/demo.duckdb"` line 6
  - `demo/iot-telemetry/profiles.yml` — same pattern
  - `demo/financial-risk/profiles.yml` — same pattern
- **Security constraint**: `readOnlyRootFilesystem: true` in values.yaml (~line 667-670)
- **Compiled output**: Already uses `path: ":memory:"` — validated by `test_dbt_profile_correct_for_in_cluster_execution`
- **DuckDB docs**: `:memory:` is fully supported, no filesystem needed
- **Gotcha**: The profiles.yml is baked into the Docker image at build time via Dockerfile COPY. The compiled artifacts' profile values are NOT written back to the image.

## Fix C: OpenLineage parentRun

- **File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
- **Line**: 582 — `extract_dbt_model_lineage(result.project_dir, run_id, model_name, lineage.namespace)`
- **Wrong**: `run_id` = `lineage.emit_start()` return value (asset-level OL UUID)
- **Correct**: `UUID(context.run.run_id)` (Dagster orchestrator run UUID)
- **Facet builder**: `packages/floe-core/src/floe_core/lineage/facets.py:228-263` — correctly implemented
- **Extraction**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py:176` — correctly implemented
- **Import**: `from uuid import UUID as _UUID` (avoid shadowing)
- **E2E test**: `test_openlineage_four_emission_points` validates via Marquez events API

## Fix D: Helm hook

- **Template**: `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml`
- **Values**: `charts/floe-platform/values.yaml:434-441` — image config
- **Unit tests**: `charts/floe-platform/tests/hook-pre-upgrade_test.yaml`
- **Setup**: `testing/k8s/setup-cluster.sh:130-144` — image pre-loads
- **Current image**: `bitnami/kubectl:1.32.0`
- **Target image**: `curlimages/curl:8.5.0` (already pre-loaded at line 135)
- **VCT labels**: Already use `immutableLabels` helper (excludes `helm.sh/chart`, `app.kubernetes.io/version`)
- **RBAC**: Role at documentIndex 1, verbs `["get", "list", "watch", "delete"]` — unchanged
- **K8s API endpoint**: `DELETE /apis/apps/v1/namespaces/{ns}/statefulsets/{name}` with body `{"propagationPolicy":"Orphan"}`
- **Bitnami issue**: bitnami/charts#36357 — stopped publishing new kubectl tags
- **Helm issue**: helm/helm#7476 — pending-upgrade sticky state

## Key file paths

| Purpose | Path |
|---------|------|
| Helm helpers | `charts/floe-platform/templates/_helpers.tpl` (immutableLabels at line 73) |
| PostgreSQL StatefulSet | `charts/floe-platform/templates/statefulset-postgresql.yaml` (VCT at line 117) |
| Plugin code | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` |
| Lineage extraction | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py` |
| Facet builders | `packages/floe-core/src/floe_core/lineage/facets.py` |
| E2E tests | `tests/e2e/` |
| Helm unit tests | `charts/floe-platform/tests/`, `charts/floe-jobs/tests/` |
| Kind setup | `testing/k8s/setup-cluster.sh` |
| Values | `charts/floe-platform/values.yaml` |
