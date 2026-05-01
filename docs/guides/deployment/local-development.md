# Local Kind Evaluation

Use local Kind when you want a disposable Kubernetes cluster for Platform Engineer evaluation or contributor smoke checks. This is not a separate product onboarding CLI path; it is the local Kubernetes form of the Helm deployment workflow.

Docker Compose is not supported because Floe's platform behavior depends on Kubernetes service discovery, workload lifecycle, and Helm rendering.

## Prerequisites

- Docker is running locally.
- `kind`, `kubectl`, and `helm` are installed.
- You are running commands from the Floe repository root.

## 1. Create The Kind Cluster

```bash
make kind-up
```

Expected outcome:

- A local Kind cluster is available.
- `kubectl cluster-info` points at the local evaluation cluster.

## 2. Render The Platform Chart

```bash
helm dependency update ./charts/floe-platform
helm template floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace >/tmp/floe-platform-rendered.yaml
```

Expected outcome:

- Helm dependencies resolve locally.
- The chart renders Kubernetes manifests without schema or template errors.

## 3. Install Floe Locally

```bash
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

Expected outcome:

- Helm reports the `floe` release as deployed.
- Platform pods begin starting in the `floe-dev` namespace.

## 4. Inspect Platform Health

```bash
kubectl get pods -n floe-dev
helm status floe -n floe-dev
```

Expected outcome:

- Required platform pods reach `Running` or `Completed`.
- Helm reports the release status as `deployed`.

## 5. Access Dagster For Evaluation

```bash
RELEASE=${RELEASE:-floe}
kubectl port-forward -n floe-dev "svc/${RELEASE}-dagster-webserver" 3100:80
```

Expected outcome:

- Dagster is reachable at `http://localhost:3100`.
- If your install uses a different release name, set `RELEASE` before running the port-forward.
- The default chart uses service port `80`; demo-specific values may override that port.

## 6. Clean Up

```bash
make kind-down
```

Expected outcome:

- The local Kind cluster is removed.
- Local evaluation resources are destroyed.

## Related Documentation

- [Platform Engineer first platform guide](../../platform-engineers/first-platform.md)
- [Kubernetes Helm](kubernetes-helm.md)
- [Capability status](../../architecture/capability-status.md)
