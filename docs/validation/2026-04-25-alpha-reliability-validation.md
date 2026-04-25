# Alpha Reliability Validation - 2026-04-25

## Scope

Validate the alpha runtime spine after the Dagster path collapse:

- manifest/floe compilation into `CompiledArtifacts`
- Dagster runtime loading from compiled artifacts
- dbt execution
- Iceberg export through Polaris/S3
- OpenLineage emission and Marquez visibility
- local Kind and DevPod/Hetzner execution paths

## Command Results

| Command | Result | Notes |
| --- | --- | --- |
| `make lint` | PASS | Passed before the Docker-context wrapper fix; rerun required before push. |
| `make typecheck` | PASS | Passed after typed YAML workflow-test fix; rerun required before push. |
| `make test-unit` | PASS | `9793 passed, 1 skipped, 1 xfailed`; coverage `87.68%`. |
| `uv run pytest tests/unit/test_public_docker_config_wrapper.py -q` | PASS | `7 passed`; covers isolated Docker config preserving active context. |
| `uv run pytest plugins/floe-orchestrator-dagster/tests/unit/test_plugin_lineage_wiring.py -v` | PASS | `16 passed`; covers artifact-driven lineage namespace propagation. |
| `PYTHONPATH="$PWD" uv run pytest plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py plugins/floe-orchestrator-dagster/tests/integration/test_loud_failure_integration.py -v` | PASS | `8 passed`; direct package-root invocation needs repo-root `PYTHONPATH`. |
| `make deploy-local` | FAIL | Target does not exist; current equivalents are `make kind-up`, `make demo-local`, and `make demo`. |
| `make kind-up` | FAIL | Local host missing `flux`; this is a host tool prerequisite issue. |
| `FLOE_NO_FLUX=1 make kind-up` | PASS | Passed after preserving the active Docker context in the public Docker config wrapper. |
| `KIND_CLUSTER_NAME=floe-test make build-demo-image` | PASS | Built and loaded `floe-dagster-demo:f1d876b79ebb-dirty-6d698d5c710f`. |
| `make test-integration` | ABORTED after deterministic failures | Test runner launched in-cluster E2E job and selected 291 tests. Run was terminated after repeated deterministic failures to avoid wasting time. |
| `make devpod-test` | FAIL before E2E | Hetzner VM was created and deleted. DevPod failed during provisioning because Flux `floe-platform` HelmRelease did not reach Ready in 15m. |

## Fixed During Validation

The local stale-image failure was caused by `scripts/with-public-docker-config.sh` replacing `DOCKER_CONFIG` with an isolated auth config that omitted the active Docker context. On OrbStack/Colima-style hosts this made Docker fall back to `/var/run/docker.sock`, so demo image builds failed even though `docker info` worked in the ambient shell.

The wrapper now captures `docker context show` before replacing `DOCKER_CONFIG`, writes `currentContext` into the isolated config, and links the source Docker `contexts` directory. This keeps public-auth builds free of ambient credentials without losing the runtime endpoint.

## Remaining Failures

### Catalog/Table Lifecycle

The direct cause of Dagster materialization failures is stale Polaris table metadata pointing at missing S3/MinIO metadata files. Dagster dbt execution completes successfully:

```text
Completed successfully
Done. PASS=40 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=40
```

The failure happens after dbt, during Iceberg export:

```text
pyiceberg.exceptions.BadRequestError: NotFoundException: Location does not exist:
s3://floe-iceberg/customer_360/int_customer_orders/metadata/00001-...
```

This is a real reliability bug at the catalog/export boundary. The runtime should recover from a broken existing table reference by dropping/recreating or otherwise repairing the table registration, or the test reset path must atomically clear catalog and object storage state together.

### Dagster Daemon Resources

The local Dagster daemon entered `CrashLoopBackOff` with `OOMKilled` exit code `137` at a `1536Mi` memory limit. This is independent of the direct Iceberg export failure but will make repeated E2E runs noisy and unreliable.

There is also a manifest-contract gap: `demo/manifest.yaml` contains top-level `resource_presets`, but `PlatformManifest` currently ignores it with a warning:

```text
Unknown fields in manifest will be ignored: ['resource_presets']
```

If resource sizing is meant to be manifest-driven, this field must be modeled in the manifest schema or moved to the correct deployment configuration contract.

### Runtime Lineage Visibility

Marquez is reachable and accepts synthetic OpenLineage events, and in-cluster lineage POSTs return `201 Created`. The product runtime check still fails at:

```text
GET /api/v1/namespaces/customer-360/jobs/customer-360/runs -> 404 Not Found
```

Likely causes are product runtime failures preventing terminal events, namespace/job naming mismatch, or both. This should be debugged after the catalog export path is stable, because failed materializations can suppress expected COMPLETE lineage.

### DevPod/Hetzner Path

`make devpod-test` did not reach E2E execution. The remote workspace built the devcontainer, created the Kind cluster, built the demo image, installed Flux, then timed out waiting for `floe-platform`:

```text
error: timed out waiting for the condition on helmreleases/floe-platform
floe-jobs-test: dependency 'floe-test/floe-platform' is not ready
```

The run also applied Flux manifests from `Obsidian-Owl/floe@feat/unit-c-devpod-runner`, not the current local branch `feat/alpha-reliability-closure`. Treat this as remote deployment readiness evidence only, not as validation of local uncommitted fixes.

## Classification

We are past the stale-image and hardcoded-manifest class of failures for the local path. The remaining blockers are production-code or deployment-contract issues:

- Polaris/Iceberg stale table recovery and test reset semantics.
- Dagster daemon resource sizing and whether resource presets are actually manifest-driven.
- Runtime OpenLineage/Marquez naming and terminal event visibility.
- DevPod Flux readiness, plus branch/source selection for remote validation.
