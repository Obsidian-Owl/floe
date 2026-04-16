# Context: Alpha RunLauncher Fix

## Research Source

`.specwright/research/alpha-remaining-bugs-20260328.md` — HIGH confidence, all 3 tracks.

## Key File Paths

### Helm Values (all need image config)
- `charts/floe-platform/values.yaml:187-201` — base defaults, run launcher section
- `charts/floe-platform/values-test.yaml:40-113` — test/CI values (Kind cluster)
- `charts/floe-platform/values-dev.yaml:44-54` — dev values
- `charts/floe-platform/values-demo.yaml:78-89` — demo values
- `charts/floe-platform/values-prod.yaml:72-81` — prod values (ALSO has snake_case bug)
- `charts/floe-platform/values-staging.yaml:70-79` — staging values (ALSO has snake_case bug)

### Dagster Subchart (READ ONLY — do not modify)
- `charts/floe-platform/charts/dagster/templates/helpers/instance/_run-launcher.tpl:79-81`
  ```
  {{- if (hasKey $k8sRunLauncherConfig "image") }}
  job_image: {{ include "dagster.externalImage.name" $k8sRunLauncherConfig.image | quote }}
  {{- end }}
  ```
- `charts/floe-platform/charts/dagster/templates/helpers/_helpers.tpl:29-31`
  ```
  {{- define "dagster.externalImage.name" }}
  {{- .repository -}}:{{- .tag -}}
  {{- end }}
  ```

### Existing Image Config (reference for consistency)
- `values-test.yaml:71-74` — webserver: `repository: floe-dagster-demo`, `tag: latest`, `pullPolicy: Never`
- `values-test.yaml:97-100` — daemon: same image

### Vulnerability Ignore
- `.vuln-ignore:29-31` — requests CVE comment (incorrect fix version)

## Gotchas

1. **snake_case vs camelCase**: Helm YAML keys are case-sensitive. `run_launcher` !=
   `runLauncher`. The Dagster chart uses camelCase. `values-prod.yaml` and
   `values-staging.yaml` have this wrong — their run launcher resources config has
   been silently ignored all along.

2. **imagePullPolicy for test**: Kind clusters use pre-loaded images. The run launcher
   image MUST use `pullPolicy: Never` (or `IfNotPresent`) since `floe-dagster-demo:latest`
   is loaded via `kind load docker-image`, not pulled from a registry.

3. **The Dagster subchart uses `imagePullPolicy` at the k8sRunLauncher level**, NOT
   inside the `image:` block. The `image:` block only has `repository` and `tag`.
   `imagePullPolicy` is a sibling key.

4. **Run pods need the same image as webserver/daemon** because they must have the
   floe demo code (definitions, dbt models) available to execute materializations.

## E2E Tests Expected to Pass After Fix

| Test | Failure Mode | Expected Resolution |
|------|-------------|-------------------|
| `test_trigger_asset_materialization` | CheckError: image is None | Direct fix |
| `test_iceberg_tables_exist_after_materialization` | No tables (mat never ran) | Cascade |
| `test_openlineage_four_emission_points` | No lineage events | Cascade |
| `test_jaeger_trace_gap_*` | No traces | Cascade |
