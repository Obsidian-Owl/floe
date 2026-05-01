# Capability Status

Floe docs use capability labels so readers can distinguish alpha-supported workflows from architecture direction.

| Status | Meaning |
| --- | --- |
| Alpha-supported | Implemented, documented, and validated in the release lane |
| Implemented primitive | Code, schema, or contract exists, but no full user workflow is promised |
| Example | Provider-specific illustration, not a requirement |
| Planned | Architecture direction that is not yet a supported workflow |

## Alpha-Supported

- Single-platform Kubernetes deployment with the `floe-platform` Helm chart.
- Customer 360 demo validation path.
- Manifest-driven platform and data product configuration for the documented alpha path.
- OpenLineage and OpenTelemetry evidence in the Customer 360 validation path.
- Dagster-centered runtime artifact pattern for the documented alpha path.
- Platform Environment Contract as the recommended documentation and CI handoff model.

## Implemented Primitives

- Data Mesh schema and contract primitives.
- Manifest inheritance fields and validation.
- Namespace strategies for centralized and data mesh lineage naming.
- `charts/floe-jobs` as a lower-level Kubernetes Job and CronJob chart.
- `examples/hello-orders` as a first-use source example.

## Planned Or Not Yet Alpha-Supported

- Multi-cluster Data Mesh deployment operations.
- A dedicated `floe-domain` Helm chart.
- Product registration commands such as `floe product register`.
- Provider-specific managed Kubernetes guides until each path is validated.
- Planned root data-team lifecycle commands as packaged product workflow: `floe compile`, `floe run`, and `floe product deploy`.
- Self-service product deployment through `floe-jobs` without Platform Engineer-approved workflow design.
