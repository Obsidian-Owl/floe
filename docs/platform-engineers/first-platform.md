# Deploy Your First Platform

This guide deploys Floe to a Kubernetes cluster you control. Floe does not require a specific cloud provider for the product path.

## Prerequisites

- `kubectl` points at the cluster where you want to deploy Floe.
- `helm` is installed locally.
- You can create namespaces, secrets, services, deployments, jobs, and persistent volume claims.
- You have decided how Floe should access object storage, catalog services, lineage, tracing, and secrets for this environment.

For local evaluation, use Kind. For real deployment, use your organization's Kubernetes platform and durable backing services.

## 1. Choose Your Environment

Use any Kubernetes cluster where you can install Helm charts and create the Floe namespace. Kind is suitable for evaluation. Managed Kubernetes is suitable when your organization supplies durable storage, ingress, TLS, identity, backup, and operational controls.

## 2. Render The Platform

```bash
helm dependency update ./charts/floe-platform
helm template floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace \
  >/tmp/floe-platform-rendered.yaml
```

## 3. Install The Platform

```bash
helm upgrade --install floe ./charts/floe-platform \
  --namespace floe-dev \
  --create-namespace
```

## 4. Wait For Services

```bash
kubectl get pods -n floe-dev
kubectl wait --for=condition=Ready pods --all -n floe-dev --timeout=10m
```

## 5. Publish The Environment Contract

Start from `examples/platform-environment-contracts/dev.yaml` and replace namespace, release name, registry, access, and URL values for your environment.

## 6. Validate The Platform

Continue with [Validate Your Platform](validate-platform.md).

## 7. Prove The Full Demo

Run [Customer 360](../demo/customer-360.md) after the basic platform and environment contract are validated.
