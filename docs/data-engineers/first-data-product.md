# Build Your First Data Product

This guide builds `hello-orders`, a minimal data product with one seed, one staging model, one mart, and dbt tests. Customer 360 is the advanced demo after you understand this path.

## Prerequisites

- A Platform Environment Contract from your Platform Engineer.
- A Floe platform installed and validated by a Platform Engineer.
- A repository checkout with the `examples/hello-orders` project.
- `uv`, Python, and the repository development dependencies installed for the alpha docs path.

## 1. Inspect The Environment Contract

```bash
sed -n '1,220p' examples/platform-environment-contracts/dev.yaml
```

## 2. Inspect The Data Product

```bash
find examples/hello-orders -maxdepth 3 -type f | sort
sed -n '1,180p' examples/hello-orders/floe.yaml
```

## 3. Review The dbt Models

```bash
sed -n '1,120p' examples/hello-orders/models/staging/stg_orders.sql
sed -n '1,120p' examples/hello-orders/models/marts/mart_daily_orders.sql
sed -n '1,180p' examples/hello-orders/models/schema.yml
```

## 4. Compile The Product For The Alpha Runtime Contract


```bash
uv run floe platform compile \
  --spec examples/hello-orders/floe.yaml \
  --manifest demo/manifest.yaml \
  --output target/hello-orders/compiled_artifacts.json \
  --generate-definitions
```

The root `floe compile`, `floe run`, and `floe product deploy` commands are planned product lifecycle entry points. They are not the current alpha path.

## 5. Package A Runtime Artifact

For the alpha path, CI should build a product runtime image that contains:

- dbt project files.
- `compiled_artifacts.json`.
- generated Dagster definitions.
- runtime dependencies pinned by the repository lockfile or organization base image.

## 6. Deploy Through Your Organization's Approved Path

Use the handoff pattern documented in [Data Product Runtime Artifacts](../guides/deployment/data-product-runtime-artifacts.md). Floe does not mandate GitHub, GitLab, Jenkins, Argo CD, Flux, Backstage, or a specific registry.

## 7. Validate The Product

Continue with [Validate Your Data Product](validate-data-product.md).

## 8. Then Run Customer 360

After `hello-orders`, use [Customer 360](../demo/customer-360.md) to prove the full business demo and release-validation path.
