# Data Product Runtime Artifacts

Floe's alpha data product deployment path should be understood as an artifact flow.

## Recommended Alpha Shape

1. Data product source lives in a product repository.
2. CI runs dbt checks and `uv run floe platform compile --spec <product>/floe.yaml --manifest <platform>/manifest.yaml --output <target>/compiled_artifacts.json --generate-definitions`.
3. CI builds a product runtime image containing product code, dbt files, compiled artifacts, and Dagster definitions.
4. CI publishes the image to the organization registry.
5. The organization deployment path updates the Dagster code location or release values to use that image.
6. Dagster launches Kubernetes work and emits OpenLineage and OpenTelemetry evidence.

## Handoff Patterns

| Pattern | Use When | Floe Contract |
| --- | --- | --- |
| GitOps PR | Platform changes are deployed from a GitOps repo | CI proposes image tag and values changes |
| CI deploy job | Your release workflow can deploy after approval | CI deploys the image and records evidence |
| Service catalog request | Platform team owns production deployment | CI publishes artifact metadata and requests deployment |
| Release train | Production changes move in scheduled batches | Artifact digest and evidence are promoted together |

## Lower-Level Primitive: floe-jobs

`charts/floe-jobs` can render Kubernetes Jobs and CronJobs for dbt, dlt, and custom workloads. Use it when your Platform Engineer has approved that pattern. Do not treat it as the default self-service alpha story until a complete product workflow is documented and validated.
