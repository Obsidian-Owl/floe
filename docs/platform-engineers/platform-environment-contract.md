# Platform Environment Contract

A Platform Environment Contract is the stable handoff between Platform Engineers, Data Engineers, CI, and release workflows.

It replaces informal endpoint sharing. Data Engineers should not need a Slack message with service URLs and hidden assumptions. They need a documented contract that says which environment exists, which platform manifest it uses, what is approved, how artifacts are named, which evidence is required, and where to escalate.

## Reference Example

See [`examples/platform-environment-contracts/dev.yaml`](https://github.com/Obsidian-Owl/floe/blob/main/examples/platform-environment-contracts/dev.yaml).

## Minimum Contents

- Environment name and Kubernetes namespace.
- Platform manifest path or OCI reference.
- Approved plugin selections and defaults.
- Approved per-transform compute choices.
- Runtime spine and artifact registry convention.
- Service account, RBAC, namespace, and secret-reference rules.
- Dagster, Marquez, Jaeger, storage, and query access URLs where appropriate.
- Required validation and promotion evidence.
- Support and escalation path.

## How Data Engineers Use It

Data Engineers use the contract to configure `platform` references, choose approved compute where allowed, understand validation expectations, and know where CI will publish runtime artifacts. The contract should be versioned with the platform environment or published from the platform repository.

## What Not To Put In It

- Raw secrets.
- Personal access tokens.
- One-off workstation paths.
- Unapproved compute accounts.
- Cloud-provider assumptions that are not true for the environment.
