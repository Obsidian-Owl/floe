# OpenChoreo and Floe Spike Results

Date: 2026-04-30

## Execution Log

| Task | Command or Action | Result | Evidence |
| --- | --- | --- | --- |
| Triage source capture | Cloned `release-v1.0`; inspected release API, CRDs, install charts, docs, and samples. | Complete | OpenChoreo has a broad Kubernetes control-plane surface with `v1alpha1` CRDs and a multi-plane install model. |
| Floe architecture review | Inspected architecture summary, platform services, plugin system, orchestrator interface, Customer 360 demo, manifest, and compiled artifact contract. | Complete | Floe's data semantics and compiled artifact handoff must remain Floe-owned; OpenChoreo is only plausible as an optional platform-control layer. |
| Recommendation gate | Scored OpenChoreo against Floe architecture and hypotheses. | Adopt candidate for bounded proof | Proof should test optional platform-control integration, not orchestrator replacement. |
| OpenChoreo proof resource generation | Pending | Pending | Pending |
| OpenChoreo render or cluster validation | Render validation complete | Three of four charts rendered locally; workflow-plane render failed because the `argo-workflows` dependency was missing after Helm reported no repo definition for `https://argoproj.github.io/argo-helm`. | Rendered manifests totaled 3,660 lines across control, data, and observability planes; workflow-plane output was 0 lines. |
| Roadmap and ADR evidence | Pending | Pending | Pending |

## Final Outcome

Outcome: In progress

Recommendation: In progress

Confidence: In progress

## Blockers

No blockers recorded at scaffold time.

## OpenChoreo Render and Install Complexity

Tool availability:

| Tool | Present | Notes |
| --- | --- | --- |
| kubectl | Yes | `/usr/local/bin/kubectl` |
| helm | Yes | `/opt/homebrew/bin/helm` |
| k3d | Yes | `/opt/homebrew/bin/k3d` |
| docker | Yes | `/usr/local/bin/docker` |

Source verification:

| Signal | Result |
| --- | --- |
| Source path | `/tmp/openchoreo-floe-source` |
| Branch | `release-v1.0` |
| Checked-out revision | `1a516d5f52c25b3c91a7e48ed55c2173e8edc070` |

Helm dependency result:

| Chart | Result | Notes |
| --- | --- | --- |
| openchoreo-control-plane | Succeeded | `helm dependency build install/helm/openchoreo-control-plane` exited 0. |
| openchoreo-data-plane | Succeeded | Downloaded `kube-prometheus-stack` from `https://prometheus-community.github.io/helm-charts`; command exited 0. |
| openchoreo-workflow-plane | Failed | `Error: no repository definition for https://argoproj.github.io/argo-helm. Please add the missing repos via 'helm repo add'` |
| openchoreo-observability-plane | Succeeded | `helm dependency build install/helm/openchoreo-observability-plane` exited 0. |

Rendered resource footprint:

| Signal | Result |
| --- | --- |
| Control-plane render line count | 2,535 |
| Data-plane render line count | 343 |
| Workflow-plane render line count | 0; render failed because `argo-workflows` was missing from `install/helm/openchoreo-workflow-plane/charts/`. |
| Observability-plane render line count | 782 |
| Dominant resource kinds | `ClusterAuthzRole` 10; `ClusterAuthzRoleBinding` 9; `Deployment` 8; `ServiceAccount` 8; `ClusterRole` 7; `ClusterRoleBinding` 7; `Certificate` 6; `ConfigMap` 6; `Issuer` 6; `Service` 6. |

Assessment:

OpenChoreo has a meaningful install footprint. This does not block adoption, but it means Floe should treat it as an optional platform integration until a platform team explicitly chooses it.
