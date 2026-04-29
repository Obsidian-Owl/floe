# Customer 360 Golden Demo

Customer 360 is the `v0.1.0-alpha.1` golden demo. The alpha release gate will prove that Floe can run a data product through orchestration, transformation, storage, lineage, tracing, and business-facing query validation.

## Prerequisites

- DevPod workspace on Hetzner is running.
- Kubeconfig is synced with `make devpod-sync`.
- The repository branch has been pushed before remote validation.
- For manual UI inspection outside an automated demo run, service tunnels are running with `make devpod-tunnels`.

## Run

```bash
make demo
```

`make demo` deploys the demo platform and services, then starts the port-forwards it needs. It does not yet trigger or validate Customer 360 outcomes. Do not start separate `make devpod-tunnels` sessions at the same time unless you are intentionally doing manual inspection outside a demo run.

Automated Customer 360 validation is added by release hardening before alpha tagging. Until then, manual validation must confirm the expected run, storage, lineage, trace, catalog, and query evidence.

## Service URLs

These URLs match the current `make demo` DevPod port-forwards.

| Service | URL | Proof |
| --- | --- | --- |
| Dagster | http://localhost:3100 | Manual validation must confirm a Customer 360 run succeeds |
| MinIO | http://localhost:9001 | Manual validation must confirm Customer 360 objects exist |
| Marquez | http://localhost:5100 | Manual validation must confirm Customer 360 lineage exists |
| Jaeger | http://localhost:16686 | Manual validation must confirm Customer 360 traces exist |
| Polaris | http://localhost:8181 | Manual validation must confirm Customer 360 tables are registered |

## Business Outcome

The final mart is `mart_customer_360`. The alpha release gate will be successful when Customer 360 outputs can be queried and lineage/tracing evidence is visible for the run.

## Next Step

- [Validate Customer 360](customer-360-validation.md)
