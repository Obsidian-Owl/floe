# Deploy Your First Platform

This guide deploys Floe to a Kubernetes cluster you control. Floe does not require a specific cloud provider for the product path.

## Prerequisites

- `kubectl` points at the cluster where you want to deploy Floe.
- `helm` is installed locally.
- You can create namespaces, secrets, services, deployments, jobs, and persistent volume claims.
- You have decided how Floe should access object storage, catalog services, lineage, tracing, and secrets for this environment.

For local evaluation, use Kind. For real deployment, use your organization's Kubernetes platform and durable backing services.

## 1. Confirm Your Cluster Context

```bash
kubectl config current-context
kubectl cluster-info
kubectl auth can-i create namespace
```

Expected outcome:

- `kubectl config current-context` shows the cluster you intend to use.
- `kubectl cluster-info` returns Kubernetes API information.
- `kubectl auth can-i create namespace` returns `yes`.

## 2. Choose The Deployment Mode

| Mode | Use When | Notes |
| --- | --- | --- |
| Evaluation | You want to inspect Floe quickly | Use Kind or another disposable cluster |
| Real Kubernetes deployment | You want Floe on managed or self-hosted Kubernetes | Bring durable storage, secrets, ingress, and backup choices |
| Contributor validation | You are developing Floe itself | Use the Floe Contributor DevPod guide |

## 3. Prepare Platform Configuration

Start with the alpha platform values that match the Customer 360 path, then replace environment-specific settings for your cluster.

```bash
helm dependency update ./charts/floe-platform
helm template floe ./charts/floe-platform --namespace floe-dev --create-namespace >/tmp/floe-platform-rendered.yaml
```

Expected outcome:

- Helm renders Kubernetes resources without schema errors.
- The rendered resources reference your selected namespace and values.

## 4. Install Floe

```bash
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

Expected outcome:

- Helm reports the release as deployed.
- Platform pods begin starting in the `floe-dev` namespace.

## 5. Wait For Platform Services

```bash
kubectl get pods -n floe-dev
kubectl wait --for=condition=Ready pods --all -n floe-dev --timeout=10m
```

Expected outcome:

- Required platform pods reach `Ready`.
- If a pod does not become ready, inspect `kubectl describe pod` and `kubectl logs` for that pod before continuing.

## 6. Validate The Platform

Continue with [Validate Your Platform](validate-platform.md).

## Cloud Provider Examples

Provider-specific guides are examples, not requirements. EKS, GKE, AKS, and other providers can all be documented after each path is validated. The alpha product contract remains Kubernetes, Helm, manifests, and Floe artifacts.
