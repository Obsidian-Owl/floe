# Platform Engineers

Platform Engineers use Floe to deploy and operate governed data platform services on Kubernetes.

## What You Own

- Kubernetes cluster access and platform namespace setup.
- Platform manifest choices for compute, catalog, storage, orchestration, lineage, observability, and security.
- Helm installation, upgrades, rollback, service access, and operational validation.
- Secrets, object storage, ingress, TLS, and persistence choices for your environment.

Your primary handoff to Data Engineers is a Platform Environment Contract. It should be versioned, reviewable, and usable by humans and CI. Avoid one-off endpoint handoffs that cannot be audited or reproduced.

## Start Here

1. [Read the enterprise operating model](../guides/operating-model.md).
2. [Deploy your first platform](first-platform.md).
3. [Publish a Platform Environment Contract](platform-environment-contract.md).
4. [Validate your platform](validate-platform.md).
5. [Run Customer 360](../demo/customer-360.md) as the advanced end-to-end proof.

## What This Path Does Not Require

You do not need DevPod to deploy Floe as a product. DevPod is a contributor and release-validation path for running heavyweight checks outside a laptop.
