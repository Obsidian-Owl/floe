# Validate Your Platform

Use this guide after installing Floe to confirm that the platform is reachable and ready for a Data Engineer to run a data product.

## Platform Health

```bash
kubectl get pods -n floe-dev
helm status floe -n floe-dev
```

Expected outcome:

- Helm release status is `deployed`.
- Platform pods are `Running` or `Completed` according to their workload type.

## Service Access

Open service access using your normal Kubernetes access pattern. For local evaluation, port-forward the services you want to inspect.

```bash
RELEASE=${RELEASE:-floe}
kubectl port-forward -n floe-dev "svc/${RELEASE}-dagster-webserver" 3100:80
```

Expected outcome:

- Dagster is reachable at `http://localhost:3100`.
- Platform service access uses your cluster access method, not a cloud-provider-specific Floe requirement.

The default chart uses Dagster service port `80`. Contributor demo values override that service port to `3000`, so contributor release-validation helpers may use a different port-forward.

## Platform Evidence

- Helm release is deployed.
- Dagster UI is reachable.
- Polaris catalog API is reachable.
- MinIO or configured object storage is reachable.
- Marquez API is reachable.
- Jaeger UI or configured trace backend is reachable.
- OTel collector is accepting traces.
- Data product runtime artifact path is defined.

## Customer 360 Platform Evidence

Run the Customer 360 validation path after the data product has been deployed and run:

This is the current alpha repo-checkout evidence validator; a packaged product command is not available yet. For platform workspaces, provide the equivalent evidence requirements and supported command for your environment.

```bash
make demo-customer-360-validate
```

Expected evidence keys:

- `platform.ready`
- `dagster.customer_360_run`
- `storage.customer_360_outputs`
- `lineage.marquez_customer_360`
- `tracing.jaeger_customer_360`
- `business.customer_count`
- `business.total_lifetime_value`

## Publish The Contract, Not A Chat Message

Publish the Platform Environment Contract after validation. The draft should already exist from the deployment step; validation turns it into the contract Data Engineers and CI can trust. At minimum it should include:

- Namespace and release name.
- Platform manifest reference.
- Approved plugins and compute choices.
- Runtime artifact registry convention.
- Dagster, Marquez, Jaeger, storage, and semantic/query service access patterns.
- Required promotion evidence.
- Support path.

Use [`examples/platform-environment-contracts/dev.yaml`](https://github.com/Obsidian-Owl/floe/blob/main/examples/platform-environment-contracts/dev.yaml) as the reference shape.
