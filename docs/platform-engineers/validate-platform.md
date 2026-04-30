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
kubectl port-forward -n floe-dev svc/dagster-webserver 3100:3000
```

Expected outcome:

- Dagster is reachable at `http://localhost:3100`.
- Platform service access uses your cluster access method, not a cloud-provider-specific Floe requirement.

## Customer 360 Platform Evidence

Run the Customer 360 validation path after the data product has been deployed and run:

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

## What To Hand To Data Engineers

Give Data Engineers:

- The Floe platform endpoint and namespace.
- The data product deployment command for your environment.
- The service URLs they can use for Dagster, lineage, traces, storage, and query validation.
- Any secrets or identities they need through your approved access process.
