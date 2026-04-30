# Start Here

Floe is an open platform for building internal data platforms: platform teams choose governed plugins and runtime standards once, while data engineers describe data products with Floe and dbt project files instead of rebuilding platform wiring for every pipeline.

## Who Floe Is For

- Platform engineers use Floe to define approved compute, catalog, storage, orchestration, observability, and security choices.
- Data engineers use Floe to build governed data products that compile into runtime artifacts and run on the platform.
- Evaluators use the alpha docs to inspect the Customer 360 reference path before deciding whether Floe fits their internal data platform needs.

## Alpha Scope

The alpha supports the documented Customer 360 demo path, DevPod + Hetzner validation, local docs validation, demo compilation, and inspection of generated dbt and Floe artifacts. It does not yet support arbitrary production deployments, unmanaged cloud accounts, every plugin combination in the catalog, or a compatibility guarantee across unpublished internal workflows.

## Four Layers

Floe uses a four-layer model: Foundation packages define schemas and plugin interfaces, Configuration artifacts select platform standards, Services deploy platform runtimes such as Dagster and catalog services, and Data jobs run dbt and data-product work on top of those services. Configuration flows downward through those layers; data-product code should not mutate platform configuration.

Read the full model in [Four-Layer Overview](../architecture/four-layer-overview.md).

## Local Kind vs DevPod + Hetzner

Use local Kind for fast smoke checks when you are validating docs, Helm wiring, or local package changes. Use DevPod + Hetzner when you need the alpha-supported remote path for the Customer 360 demo, a clean Linux workspace, more predictable container resources, or release evidence that should not depend on a developer laptop.

## Choose Your Journey

- Start with [Deploy Your First Platform](../get-started/first-platform.md) if you need the remote DevPod + Hetzner workspace and Kubernetes access first.
- Start with [Build Your First Data Product](../get-started/first-data-product.md) if you want to understand how `floe.yaml`, dbt, and compiled artifacts fit together.
- Run [Customer 360](../demo/customer-360.md) when the platform path is ready and you want the alpha golden demo.
- Review the [Plugin Catalog](../reference/plugin-catalog.md) when you need to understand which platform capabilities are enforced or pluggable.
