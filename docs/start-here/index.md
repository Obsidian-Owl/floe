# Start Here

Floe is an open platform for building internal data platforms. Platform Engineers choose governed plugins and runtime standards once, while Data Engineers describe data products with Floe and dbt project files instead of rebuilding platform wiring for every pipeline.

## Who Floe Is For

- Platform Engineers use Floe to define approved compute, catalog, storage, orchestration, observability, and security choices.
- Data Engineers use Floe to build governed data products that compile into runtime artifacts and run on the platform.
- Floe Contributors use the repository, local development tools, and remote validation lanes to change Floe itself.

## Alpha Scope

The alpha supports the documented Customer 360 path, provider-neutral Kubernetes deployment guidance, local docs validation, demo compilation, and inspection of generated dbt and Floe artifacts. It does not yet claim arbitrary production readiness, every plugin combination in the catalog, or validated multi-cluster Data Mesh operations.

## Four Layers

Floe uses a four-layer model: Foundation packages define schemas and plugin interfaces, Configuration artifacts select platform standards, Services deploy platform runtimes such as Dagster and catalog services, and Data jobs run dbt and data-product work on top of those services. Configuration flows downward through those layers; data-product code should not mutate platform configuration.

Read the full model in [Four-Layer Overview](../architecture/four-layer-overview.md).

## Choose Your Journey

- Choose [Platform Engineers](../platform-engineers/index.md) if you deploy and operate Floe platforms.
- Choose [Data Engineers](../data-engineers/index.md) if you build data products on an existing Floe platform.
- Choose [Floe Contributors](../contributing/index.md) if you change Floe itself or run release validation.

## Deployment Model

Floe's product deployment model is bring any conformant Kubernetes cluster. DevPod is a contributor and release-validation workspace, not a product requirement.
