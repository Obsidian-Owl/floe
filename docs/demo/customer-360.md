# Customer 360 Golden Demo

Customer 360 is the `v0.1.0-alpha.1` golden demo. The alpha release gate will prove that Floe can run a data product through orchestration, transformation, storage, lineage, tracing, and business-facing query validation.

Platform Engineers and Data Engineers should run Customer 360 against a Floe platform that has already been deployed and made reachable through their platform access method. Floe Contributors can use the remote DevPod lane when they need release-validation evidence.

## Prerequisites

- A Floe platform is deployed and reachable.
- The Customer 360 data product has been compiled or is available in the demo project.
- You can access Dagster, object storage, Marquez, Jaeger, Polaris, and the semantic/query layer through your platform access method.

## Run

For Platform Engineers and Data Engineers, use the deployment and run trigger provided for your platform, then run the evidence validator:

```bash
make demo-customer-360-validate
```

For Floe Contributors running the remote release-validation lane:

```bash
make demo
make demo-customer-360-run
make demo-customer-360-validate
make demo-stop
```

The Customer 360 demo flow is intentionally explicit:

- `make demo` is contributor-only. It deploys the demo platform and services through DevPod, builds and loads the demo Dagster image, installs the Helm chart, and starts the required port-forwards.
- `make demo-customer-360-run` should launch the Customer 360 Dagster job declared in `demo/customer-360/validation.yaml` and wait for the run to finish.
- `make demo-customer-360-validate` runs the release evidence checks for platform readiness, Dagster run evidence, storage outputs, lineage, tracing, and business metrics.
- `make demo-stop` stops the port-forwards created by `make demo`.

The runner and validator load their default configuration from `demo/customer-360/validation.yaml`. Override that manifest or individual validation commands when validating a different platform shape. Do not start separate `make devpod-tunnels` sessions at the same time unless you are intentionally doing manual inspection outside a demo run.

## Service URLs

These URLs match the current contributor `make demo` DevPod port-forwards. Product deployments should use the service URLs or ingress routes supplied by the Platform Engineer.

| Service | URL | Proof |
| --- | --- | --- |
| Dagster | http://localhost:3100 | Customer 360 run succeeds |
| MinIO | http://localhost:9001 | Customer 360 output objects exist |
| Marquez | http://localhost:5100 | Customer 360 lineage exists |
| Jaeger | http://localhost:16686 | Customer 360 traces exist |
| Polaris | http://localhost:8181 | Customer 360 tables are registered |

## Business Outcome

The final mart is `mart_customer_360`. The alpha release gate will be successful when Customer 360 outputs can be queried and lineage/tracing evidence is visible for the run.

## Next Step

- [Validate Customer 360](customer-360-validation.md)
