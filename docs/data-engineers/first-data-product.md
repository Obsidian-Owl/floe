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

```bash
uv run floe data validate demo/customer-360/floe.yaml
```

Expected outcome:

- Floe reports schema-valid product configuration.
- Validation errors point to fields in `floe.yaml` that need correction.

## 3. Compile The Product

```bash
uv run floe data compile demo/customer-360/floe.yaml --output target/customer-360
```

Expected outcome:

- Floe writes compiled artifacts under `target/customer-360`.
- The artifacts are the handoff contract for orchestration, dbt, lineage, and platform services.

## 4. Run The Product

Use the run command or deployment command documented by your Platform Engineer for the target platform. For the alpha Customer 360 path, use the Customer 360 demo guide:

```bash
make demo-customer-360-run
```

Expected outcome:

- The Customer 360 run completes successfully.
- The platform records run, lineage, trace, storage, and business output evidence.

## 5. Validate The Product Outputs

Continue with [Validate Your Data Product](validate-data-product.md).
