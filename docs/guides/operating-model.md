# Recommended Enterprise Operating Model

Floe fits into an enterprise delivery system. It does not replace your source control, CI/CD, artifact registry, release approvals, identity provider, service catalog, or GitOps controller.

## Roles

| Role | Owns | Does Not Own |
| --- | --- | --- |
| Platform Engineer | Platform environments, manifests, plugin defaults, service health, access boundaries, environment contracts | Product SQL logic and product business tests |
| Data Engineer | `floe.yaml`, dbt models, product tests, product contracts, product run validation | Platform service credentials, cluster-wide policy, production access bypasses |
| Governance, Security, Release | Approval rules, exception handling, evidence requirements, production controls | Day-to-day product modeling |

## Recommended Flow

1. Platform Engineer publishes a Platform Environment Contract.
2. Data Engineer creates a product repo and targets that contract.
3. Pull request runs dbt checks, Floe compilation, policy checks, and docs/artifact validation.
4. CI builds a runtime artifact, usually a container image for the alpha Dagster path.
5. CI publishes the artifact to the organization registry.
6. Approval happens through the organization's release process.
7. Deployment happens through GitOps, CI deployment, service catalog, or a release train.
8. Dagster or the selected runtime launches Kubernetes work.
9. OpenLineage and OpenTelemetry provide evidence of what ran.
10. Data Engineer validates business outputs and escalates platform failures with evidence.

## What Floe Standardizes

- Platform and data product configuration contracts.
- Compile-time validation.
- Runtime artifact contract.
- Policy and data contract evidence.
- OpenLineage and OpenTelemetry expectations.
- Kubernetes-native execution model.

## What Your Organization Supplies

- Git provider and repository rules.
- CI/CD runner and approval gates.
- Container and artifact registry.
- Production deployment mechanism.
- Identity, secrets, ingress, TLS, backup, and audit controls.

## Alpha Posture

The recommended alpha runtime spine is Dagster because the Customer 360 release-validation path proves that shape today. `floe-jobs` is an implemented lower-level Helm primitive for Kubernetes Jobs and CronJobs, but it is not yet the primary self-service product deployment workflow.
