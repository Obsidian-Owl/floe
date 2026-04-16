# Research Brief: Dagster K8sRunLauncher Materialization Failure

**Topic ID**: dagster-materialization-failure
**Date**: 2026-03-28
**Triggered by**: E2E test failures — `test_trigger_asset_materialization` and `test_iceberg_tables_exist_after_materialization`
**Confidence**: HIGH (official docs + codebase inspection)

## Context

Despite PR #211 fixing the K8sRunLauncher image configuration (adding `image.repository` and `image.tag` to values files), asset materialization still fails in E2E tests. The run worker pod **launches** (image config is correct) but the run itself ends with status `FAILURE`.

Run ID from last E2E: `8f4e1ef2-5289-444d-87fb-b9d8bd2c32b3`

## Research Tracks

### Track 1: K8sRunLauncher Run Worker Pod Architecture

**Confidence: HIGH** — Official Dagster docs

The K8sRunLauncher creates a **separate Kubernetes Job** for every Dagster run. Key facts:

1. **Run worker pods are ephemeral** — created per-run, run `dagster api execute_run`, then exit.
2. **Environment variables from daemon/webserver are NOT automatically available** in run worker pods unless configured via:
   - `includeConfigInLaunchedRuns` (enabled by default since Dagster 0.15.0) — serializes user code deployment env vars into `DAGSTER_CLI_API_GRPC_CONTAINER_CONTEXT`
   - `env_config_maps` / `env_secrets` / `env_vars` on the run launcher config
3. **Dagster instance config** comes from a mounted ConfigMap (`instance_config_map`), not from the daemon's environment.
4. **Volumes/volume mounts** must be explicitly configured on the run launcher or via `runK8sConfig`.

Sources:
- https://docs.dagster.io/integrations/libraries/k8s/dagster-k8s
- https://github.com/dagster-io/dagster/issues/3102

### Track 2: Our Specific Configuration Gap

**Confidence: HIGH** — Direct codebase inspection

Our `values-test.yaml` configures:
```yaml
runLauncher:
  type: K8sRunLauncher
  config:
    k8sRunLauncher:
      image:
        repository: floe-dagster-demo
        tag: latest
        pullPolicy: Never
      imagePullPolicy: Never
```

But does **NOT** configure:
- `envConfigMaps` (empty list at values.yaml line 199)
- `envSecrets` (empty list at values.yaml line 200)
- `env_vars` — not set
- `volumeMounts` — not set
- `volumes` — not set

The dbt project files are accessed via relative paths from the Python module:
```python
PROJECT_DIR = Path(__file__).parent
DBT_PROJECT_DIR = PROJECT_DIR
```

This means **everything must be baked into the Docker image** at `/app/demo/{product}/`. The image `floe-dagster-demo:latest` must contain:
- All three demo product directories
- `profiles.yml` and `dbt_project.yml` per product
- All Python dependencies (dbt-core, dbt-duckdb, PyIceberg, etc.)
- PYTHONPATH including `/app/demo`

### Track 3: Polaris Bootstrap Failure (Likely Root Cause)

**Confidence: HIGH** — Captured in test-logs

Test logs reveal a **Polaris bootstrap failure**:

```
[2026-03-14T22:40:11Z] BOOTSTRAP: Step 7/7: Assigning catalog role 'catalog_admin' to principal role 'ALL'...
[2026-03-14T22:40:11Z] BOOTSTRAP: ERROR: Failed to assign catalog role (HTTP 404)
{"error":{"message":"Entity ALL not found when trying to assign floe-e2e.catalog_admin to ALL"}}
```

The bootstrap script tries to assign catalog_admin to a principal role named "ALL" which doesn't exist. Without this assignment, the Dagster job cannot write Iceberg tables to Polaris.

The `polaris_client` E2E fixture applies write grants defensively (5-step process), but this is for the test client — the **run worker pod** needs its own access.

### Track 4: How to Debug the Actual Run Failure

**Confidence: HIGH** — Official Dagster docs

To extract the actual failure reason:

**kubectl approach** (find run worker pod by run ID):
```bash
kubectl get pods -n floe-test -l dagster/run-id=8f4e1ef2-5289-444d-87fb-b9d8bd2c32b3
kubectl logs -n floe-test -l dagster/run-id=8f4e1ef2-5289-444d-87fb-b9d8bd2c32b3 --tail=100
```

**GraphQL approach** (query failure events):
```graphql
query GetLogsForRun($runId: ID!) {
  logsForRun(runId: $runId) {
    ... on EventConnection {
      events {
        __typename
        ... on ExecutionStepFailureEvent {
          message
          stepKey
          error { message stack }
        }
        ... on RunFailureEvent {
          message
          pipelineFailureError: error { message stack }
        }
      }
    }
  }
}
```

**Dagster CLI** (export all run data):
```bash
dagster debug export <run-id> debug_output.gz
```

Sources:
- https://docs.dagster.io/api/graphql
- https://github.com/dagster-io/dagster/discussions/26011

## Synthesis: Most Likely Failure Causes (Ranked)

1. **Polaris write permissions not granted** — Bootstrap failed to assign catalog_admin role. Run worker pod cannot write Iceberg tables even if dbt runs successfully. The E2E fixture grants permissions to the test client but NOT to the run worker pod's identity.

2. **Missing environment variables in run pod** — If Polaris credentials, S3 endpoints, or database connection strings are needed as env vars and aren't baked into the image or passed via `env_config_maps`/`env_secrets`, the run will fail.

3. **dbt profile connectivity** — The `profiles.yml` uses `:memory:` for DuckDB (confirmed in code), so dbt execution itself should work. But writing results to Iceberg/Polaris requires the Polaris REST catalog to be reachable AND authorized from the run pod.

4. **Python dependency mismatch** — If `floe-dagster-demo:latest` was rebuilt without all required packages (dagster-dbt, dbt-duckdb, pyiceberg), imports fail at run time.

## Recommended Investigation Steps

1. **Check if the run worker pod still exists** — `kubectl get pods -n floe-test -l dagster/run-id=8f4e1ef2-*` (pods may be cleaned up)
2. **Query Dagster GraphQL for run failure events** — Use the `logsForRun` query above against the Dagster webserver
3. **Check Polaris bootstrap logs** — Verify if the latest deployment fixed the "Entity ALL" error
4. **Inspect the floe-dagster-demo image** — `docker run --rm floe-dagster-demo:latest ls /app/demo/` to verify files are present

## Live Debugging Results (2026-03-28)

### Issue 1: Missing `job_image` in deployed dagster.yaml (FIXED)

The deployed configmap had no `job_image` because the Dagster subchart was extracted
incorrectly (missing `Chart.yaml`). After properly extracting the subchart and running
`helm upgrade`, the configmap correctly renders `job_image: "floe-dagster-demo:latest"`.

Error before fix:
```
CheckError: Value in Mapping mismatches expected type for key dagster/image.
Expected value of type <class 'str'>. Got value None of type <class 'NoneType'>.
```

### Issue 2: `@dbt_assets(project=DbtCliResource(...))` type mismatch (ROOT CAUSE)

After fixing `job_image`, the run worker pod launches but the run fails with:
```
ParameterCheckError: Param "dbt_project" is not a DbtProject.
Got DbtCliResource(project_dir='/app/demo/customer_360', ...)
which is type <class 'dagster_dbt.core.resource.DbtCliResource'>.
```

The `@dbt_assets` decorator's `project=` parameter requires `DbtProject`, not `DbtCliResource`.
All three demo definitions (`customer-360`, `financial-risk`, `iot-telemetry`) had this bug.

**Fix**: Change `project=DbtCliResource(project_dir=...)` to
`project=DbtProject(project_dir=..., profiles_dir=...)` and add `DbtProject` import.

### Polaris Bootstrap Error (STALE)

The "Entity ALL not found" error from test logs was from 2026-03-14 and is no longer
the blocking issue. The fresh cluster deployment does not show this error.

## Caveats

- `DbtProject` does not respect `DBT_PROFILES_DIR` env var — must pass `profiles_dir`
  explicitly (dagster-io/dagster#26504).
- `includeConfigInLaunchedRuns` behavior depends on the exact Dagster Helm chart version
  (1.12.17 in our chart).
