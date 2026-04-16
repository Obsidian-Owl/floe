# Assumptions: Alpha RunLauncher Fix

## A1: Run pod image should match webserver/daemon image
- **Type**: Technical
- **Status**: ACCEPTED
- **Confidence**: HIGH
- **Evidence**: `python_module` code locations require the floe demo code (Python
  modules, dbt project) to be present in the run pod. The `floe-dagster-demo` image
  contains all of this. Using a different image would require a separate build pipeline.
- **Resolution**: Auto-accepted — single valid approach for `python_module` pattern.

## A2: imagePullPolicy: Never is correct for Kind test clusters
- **Type**: Technical
- **Status**: ACCEPTED
- **Confidence**: HIGH
- **Evidence**: Kind clusters use `kind load docker-image` to pre-load images. The
  `floe-dagster-demo:latest` image is not in any registry — it's built locally and
  loaded into the Kind node. `pullPolicy: Never` prevents K8s from trying to pull
  from a registry (which would fail).
- **Resolution**: Auto-accepted — matches existing webserver/daemon config at
  `values-test.yaml:74`.

## A3: Dagster subchart renders image config via hasKey check
- **Type**: Reference
- **Status**: ACCEPTED
- **Confidence**: HIGH
- **Evidence**: Verified in `_run-launcher.tpl:79-81`:
  `{{- if (hasKey $k8sRunLauncherConfig "image") }}`.
  The `dagster.externalImage.name` helper formats as `repository:tag`.
- **Resolution**: Verified against subchart source code.

## A4: OpenLineage parentRun failures will resolve as cascade
- **Type**: Clarify
- **Status**: ACCEPTED
- **Confidence**: HIGH
- **Evidence**: Research Track 2 confirmed the parentRun facet code is correctly
  wired at `plugin.py:585-590` → `lineage_extraction.py:216-220`. It never executes
  because the materialization fails first. No code changes needed.
- **Resolution**: Auto-accepted — code path verified in research. E2E verification
  will confirm after fix.

## A5: requests CVE is not exploitable in floe
- **Type**: Technical
- **Status**: ACCEPTED
- **Confidence**: HIGH
- **Evidence**: CVE-2026-25645 affects `extract_zipped_paths()` only. Floe does not
  use this function. `datacontract-cli` upper-bounds `requests<2.33`, blocking the fix.
- **Resolution**: Keep in `.vuln-ignore` with corrected comment. Track upstream.
