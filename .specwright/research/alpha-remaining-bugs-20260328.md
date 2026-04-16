# Research Brief: Remaining Alpha Bugs

**Date**: 2026-03-28
**Tracks**: 3 (Dagster K8sRunLauncher, OpenLineage parentRun, requests CVE)
**Confidence**: HIGH (all tracks verified against source code + official docs)
**Consumer**: sw-design for alpha stability fixes

---

## Track 1: Dagster K8sRunLauncher Image Resolution

**Confidence**: HIGH

### Problem
`test_trigger_asset_materialization` fails because `dagster/image` tag is `None` →
`CheckError` in K8sRunLauncher before any dbt models execute.

### Root Cause
Floe uses `python_module` code locations (not gRPC server deployments). With
`python_module` loading, code runs **in-process** with webserver/daemon — there is
no separate gRPC server pod, so `DAGSTER_CURRENT_IMAGE` has no effect and
`repository_origin.container_image` is **always None**.

The K8sRunLauncher's Helm values (`values.yaml:187-201`) configure only
`imagePullPolicy: Always` and `resources` — no `image.repository` or `image.tag`.

### Key Facts
- `DAGSTER_CURRENT_IMAGE` only works on gRPC server pods (official Dagster docs)
- Webserver/daemon images do NOT auto-propagate to run launcher
- The Dagster Helm chart supports an explicit `image:` block under
  `runLauncher.config.k8sRunLauncher` (commented out by default in upstream values.yaml)
- The floe demo image is `floe-dagster-demo:latest` (built by `make build-demo-image`)
- Dagster version: chart `1.12.17`, Python `1.12.14`, dagster-k8s `0.28.14`

### Fix Path
Set `runLauncher.config.k8sRunLauncher.image.repository` and `.tag` in values files
to match the demo image. For test: `floe-dagster-demo:latest`. For prod: parameterize.

### Sources
- [dagster-k8s integration docs](https://docs.dagster.io/integrations/libraries/k8s/dagster-k8s)
- [workspace.yaml reference](https://docs.dagster.io/deployment/code-locations/workspace-yaml)
- [dagster/helm/dagster/values.yaml](https://github.com/dagster-io/dagster/blob/master/helm/dagster/values.yaml)

### Relevant Files
- `charts/floe-platform/values.yaml:187-208`
- `charts/floe-platform/values-test.yaml:53-113`
- `charts/floe-platform/templates/configmap-dagster-workspace.yaml`
- `docker/dagster-demo/Dockerfile`

---

## Track 2: OpenLineage parentRun Facet Wiring

**Confidence**: HIGH

### Problem
`test_openlineage_four_emission_points` fails — parentRun facet not found in
Marquez run data.

### Current Code Path (ALREADY WIRED)
The production code correctly wires the parentRun facet:

1. `plugin.py:585` — `dagster_parent_id = UUID(context.run.run_id)`
2. `plugin.py:586-590` — passes to `extract_dbt_model_lineage(project_dir, dagster_parent_id, model_name, namespace)`
3. `lineage_extraction.py:216-220` — builds `ParentRunFacetBuilder.from_parent(parent_run_id, parent_job_name, parent_job_namespace)`
4. `lineage_extraction.py:240` — attaches as `run = LineageRun(run_id=model_run_id, facets={"parentRun": parent_facet})`
5. `events.py:210-211` — serializes to wire format under `run.facets`

### Why It Still Fails
The parentRun wiring code is present but **it never executes** because the Dagster
materialization itself fails (Track 1 — K8sRunLauncher `None` image). No dbt models
run → no lineage events emitted → no parentRun facets in Marquez.

This is a **cascading failure from Track 1**, not an independent bug.

### Potential Secondary Issue
The test (`test_observability.py:1059-1092`) searches for `parentRun` in multiple
locations within the Marquez response. If Marquez returns facets differently than
expected, the test may still fail even after Track 1 is fixed. This needs E2E
verification after the K8sRunLauncher fix.

### OpenLineage ParentRunFacet Spec
- Required: `run.runId` (UUID string), `job.namespace`, `job.name`
- Optional: `root` (for 3-level hierarchies)
- Schema: `https://openlineage.io/spec/facets/1-1-0/ParentRunFacet.json`
- Note: floe's `_schemaURL` references `1-0-1`, not `1-1-0` (minor)

### Relevant Files
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:580-595`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py:176-275`
- `packages/floe-core/src/floe_core/lineage/facets.py:229-263`
- `packages/floe-core/src/floe_core/lineage/events.py:174-234`
- `tests/e2e/test_observability.py:1059-1092`

---

## Track 3: requests CVE (GHSA-gc5v-m9x4-r6x2)

**Confidence**: HIGH

### Problem
`test_pip_audit_clean` fails because `requests==2.32.5` has CVE-2026-25645.

### Key Facts
- Fix requires `requests>=2.33.0` (not `>=2.32.6` as `.vuln-ignore` states — no 2.32.6 exists)
- Current lock: `requests==2.32.5`
- **Blocker**: `datacontract-cli` declares `"requests>=2.31,<2.33"` — hard upper bound
- Latest `datacontract-cli` (0.11.7, 2026-03-24) still carries the `<2.33` constraint
- No upstream fix is available — the constraint exists on `datacontract-cli` main branch
- The CVE is low-risk: only `extract_zipped_paths()` is affected, which floe doesn't use

### Options
1. **Wait for upstream** — `datacontract-cli` lifts `<2.33`. Unknown timeline.
2. **Pin override** — Use uv `override-dependencies` to force `requests>=2.33.0`,
   accepting risk that `datacontract-cli` may break with requests 2.33.
3. **Keep in vuln-ignore** — The CVE is not exploitable in floe's usage. Update the
   ignore comment to note the correct fix version (2.33.0, not 2.32.6).
4. **Bump datacontract-cli** — Fork or contribute upstream PR to lift the constraint.

### Sources
- [CVE-2026-25645 / GHSA-gc5v-m9x4-r6x2](https://github.com/advisories/GHSA-gc5v-m9x4-r6x2)
- [requests 2.33.0 on PyPI](https://pypi.org/project/requests/)
- [datacontract-cli pyproject.toml](https://github.com/datacontract/datacontract-cli/blob/main/pyproject.toml)

### Relevant Files
- `pyproject.toml` (root) — constraint-dependencies
- `packages/floe-core/pyproject.toml:46` — `datacontract-cli>=0.10.0,<1.0`
- `.vuln-ignore:29-31`
- `uv.lock:4862` — `requests==2.32.5`

---

## Synthesis: Path to Alpha

**Critical fix (unblocks 4 of 7 failures)**: Set K8sRunLauncher image in Helm values.
This fixes:
- `test_trigger_asset_materialization` (direct)
- `test_iceberg_tables_exist_after_materialization` (cascade)
- `test_openlineage_four_emission_points` (cascade — materializations must run for lineage)
- `test_jaeger_trace_gap_*` (cascade — no runs = no traces)

**Already fixed (3 of 7)**: Profile isolation test assertions (committed in `488cd2e`).

**requests CVE**: Not exploitable in floe, blocked by upstream. Recommend option 3
(keep in vuln-ignore with corrected comment) for alpha, pursue option 4 for beta.

**Net result after K8sRunLauncher fix**: 230/230 E2E tests passing (alpha-ready).

---

## Open Questions

1. Should the K8sRunLauncher image be the same as the webserver/daemon image, or a
   separate purpose-built run worker image?
2. For Kind (test), the image is `floe-dagster-demo:latest` with `pullPolicy: Never`.
   For prod, this needs to be parameterized. What registry/tag strategy?
3. The `_schemaURL` for ParentRunFacet references `1-0-1` — should we update to `1-1-0`?
