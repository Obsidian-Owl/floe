# Troubleshooting

Use this guide when the contributor remote-validation lane or Customer 360 evidence checks fail after the normal setup steps.

## Prerequisites

- Run commands from the repository root.
- Know whether you are using local Kind or the contributor remote workspace.
- For DevPod debugging, sync kubeconfig first with `make devpod-sync`.
- Keep exact command output for release evidence or follow-up issues.

## What This Does

This page separates infrastructure reachability, kubeconfig/tunnel problems, Dagster run state, log evidence, metric evidence, lineage evidence, trace evidence, and stale image symptoms so you can fix the layer that failed instead of rerunning the whole workflow blindly.

## Steps

```bash
make docs-validate
make devpod-status
export KUBECONFIG="${DEVPOD_KUBECONFIG:-$HOME/.kube/devpod-${DEVPOD_WORKSPACE:-floe}.config}"
kubectl cluster-info
kubectl get pods -n floe-dev
kubectl get pods -n floe-test
```

## Expected Output

- `make docs-validate` passes before runtime debugging starts.
- `make devpod-status` prints workspace, tunnel, and cluster sections.
- `kubectl cluster-info` reaches the synced DevPod cluster or clearly fails at the kubeconfig/tunnel boundary.
- Pod listings show whether failures are in `floe-dev` demo services or `floe-test` test infrastructure.

## Troubleshooting

| Symptom | Likely cause | Recovery |
| --- | --- | --- |
| DevPod unreachable | Workspace stopped, source not pushed, provider not configured, or DevPod transport dropped | Run `make devpod-status`, then `make devpod-up`; if source resolution fails, push the branch or set `DEVPOD_SOURCE` |
| Stale or wrong kubeconfig | Local shell still points at another cluster or an old `devpod-*.config` | Run `make devpod-sync`, export `KUBECONFIG="${DEVPOD_KUBECONFIG:-$HOME/.kube/devpod-${DEVPOD_WORKSPACE:-floe}.config}"`, then run `kubectl cluster-info` |
| Tunnel port in use | A prior `make demo`, `make devpod-tunnels`, or kube API tunnel still owns the local port | Run `make demo-stop`; inspect with `make devpod-status`; stop manual tunnels with `scripts/devpod-tunnels.sh --kill` if needed |
| Dagster reachable but no Customer 360 run | The demo deployment is up, but the Customer 360 job was not triggered or the image contains stale definitions | Re-run the documented Customer 360 trigger path, then check Dagster run history and rebuild the demo image if definitions do not match the current branch |
| Marquez missing final mart lineage | OpenLineage emission did not reach Marquez, the run is incomplete, or stale compiled artifacts selected the wrong lineage backend | Confirm the Dagster run succeeded, re-run `make compile-demo`, check `demo/customer-360/compiled_artifacts.json`, and inspect Marquez at `http://localhost:5100` |
| Jaeger missing trace | OpenTelemetry collector or Jaeger query service is not reachable, or the run used an image without current instrumentation | Check `kubectl get pods -n floe-dev`, confirm the `16686` tunnel, and rebuild/redeploy the demo image if traces are absent for new runs |
| Loki or Grafana logs missing | Log backend URL, collector log pipeline, or tunnel is unavailable, or the query uses the wrong product/run ID | Query `{job=~".+"} |= "customer-360" |= "<run-id>"`; if the backend is unreachable, check the log backend service and collector pods before rerunning Customer 360 |
| Prometheus or Grafana metrics missing | Metrics backend URL, collector metrics pipeline, or dashboard query is wrong, or the run has no current asset envelope metrics | Query `floe_asset_materializations_total{floe_product_name="customer-360",floe_status="success",floe_plugin_name=~".+"}` and check collector/Prometheus reachability |
| Observability validator reports `backend_unreachable` | The backend API could not be reached at the configured URL | Fix service readiness, port-forwarding, tunnel, or validation manifest URLs first; rerunning the product will not fix an unreachable backend |
| Observability validator reports `no_fresh_evidence` | Backend is reachable but no records match the product/run/table context | Confirm `dagster.run_id`, `FLOE_DEMO_RUN_ID`, exporter wiring, and that the Customer 360 run finished after the freshness cutoff |
| Observability validator reports `stale_evidence` | Matching records exist only outside the freshness window | Trigger a new Customer 360 run, then validate with the new run ID from `.customer360-run.env` |
| Observability validator reports `wrong_context` | Records exist for another product, run, table, service URL, or cluster | Check `demo/customer-360/validation.yaml`, service URLs, namespace/job names, and the run ID before changing code |
| Observability validator reports `product_failure` | Backend evidence shows the product or model/table execution failed | Debug Dagster, dbt, storage, and lineage run status first; this is product/runtime failure evidence, not a backend outage |
| Stale demo image symptoms | UI shows old assets, Dagster definitions do not match local files, generated artifact changes were not rebuilt into the image, or validation expects a newer tag | Run `make compile-demo`, rebuild through the demo path, and confirm `FLOE_DEMO_IMAGE_TAG` matches the image loaded in the workspace |

## Evidence To Capture

Include the command and the smallest useful output snippet:

```bash
make devpod-status
kubectl get pods -n floe-dev
kubectl logs -n floe-dev deploy/floe-platform-dagster-webserver --tail=100
cat .customer360-run.env
```

## Next Step

- [Review reference material](../reference/index.md)
