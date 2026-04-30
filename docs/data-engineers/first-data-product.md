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

Use the run command or deployment command documented by your Platform Engineer for the target platform. For the alpha Customer 360 evidence path, use the Customer 360 validation command after the platform and job are available:

```bash
make demo-customer-360-validate
```

Expected outcome:

- The platform reports run, lineage, trace, storage, and business output evidence for Customer 360.
- If the run has not happened yet, use the run trigger documented by your Platform Engineer or the contributor release-validation lane.

## 5. Validate The Product Outputs

Continue with [Validate Your Data Product](validate-data-product.md).
