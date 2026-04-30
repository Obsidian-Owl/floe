# Build Your First Data Product

This guide starts from an existing Floe platform. A Platform Engineer should already have deployed and validated the platform.

## Prerequisites

- Access to the target Floe platform.
- A data product project with `floe.yaml`.
- dbt project files for the product transformations.
- Access to the approved compute, storage, catalog, lineage, and observability integrations for the platform.

## 1. Inspect The Product Configuration

```bash
ls demo/customer-360
sed -n '1,160p' demo/customer-360/floe.yaml
```

Expected outcome:

- The product declares its name, owner, inputs, outputs, and runtime expectations in `floe.yaml`.
- dbt models live with the product source.

## 2. Validate The Product

The root `floe validate` command currently exists as an alpha stub and is not yet the supported Customer 360 validation path. Use the checked-in demo validation commands for the current alpha.

```bash
make compile-demo
```

Expected outcome:

- dbt manifests compile for the Customer 360 demo project.
- Floe generates `demo/customer-360/compiled_artifacts.json` and validates the generated demo artifacts.

## 3. Compile The Product

The root `floe compile` command is also an alpha data-team stub. Customer 360 compilation currently runs through the platform compiler used by `make compile-demo`.

```bash
uv run floe platform compile \
  --spec demo/customer-360/floe.yaml \
  --manifest demo/manifest.yaml \
  --output demo/customer-360/compiled_artifacts.json \
  --generate-definitions
```

Expected outcome:

- Floe writes `demo/customer-360/compiled_artifacts.json`.
- The artifacts are the handoff contract for orchestration, dbt, lineage, and platform services.

## 4. Run The Product

For `v0.1.0-alpha.1`, the supported Customer 360 path is a repo-checkout evidence path, not a packaged self-service deployment command. A Platform Engineer first deploys the Floe platform/runtime, loads the Customer 360 Dagster code, and exposes Dagster at the URL configured in `demo/customer-360/validation.yaml`. The default Dagster URL is `http://localhost:3100`.

After the platform/runtime is reachable, trigger and validate Customer 360 from the repository checkout:

```bash
make demo-customer-360-run
make demo-customer-360-validate
```

Expected outcome:

- The platform reports run, lineage, trace, storage, and business output evidence for Customer 360.
- `make demo-customer-360-run` launches the Dagster job using `demo/customer-360/validation.yaml`.
- `make demo-customer-360-validate` checks the run evidence and business outputs.
- Packaged/self-service data-product deployment commands are planned and not yet alpha-supported.

If your platform does not expose Dagster at `http://localhost:3100`, copy `demo/customer-360/validation.yaml`, edit the service URLs for your environment, and pass the copied manifest to the Python runner and validator:

```bash
uv run python -m testing.ci.run_customer_360_demo \
  --validation-manifest /path/to/customer-360-validation.yaml
uv run python -m testing.ci.validate_customer_360_demo \
  --validation-manifest /path/to/customer-360-validation.yaml
```

## 5. Validate The Product Outputs

Continue with [Validate Your Data Product](validate-data-product.md).
