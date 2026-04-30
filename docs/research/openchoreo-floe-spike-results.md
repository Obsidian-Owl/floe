# OpenChoreo and Floe Spike Results

Date: 2026-04-30

## Execution Log

| Task | Command or Action | Result | Evidence |
| --- | --- | --- | --- |
| Triage source capture | Cloned `release-v1.0`; inspected release API, CRDs, install charts, docs, and samples. | Complete | OpenChoreo has a broad Kubernetes control-plane surface with `v1alpha1` CRDs and a multi-plane install model. |
| Floe architecture review | Inspected architecture summary, platform services, plugin system, orchestrator interface, Customer 360 demo, manifest, and compiled artifact contract. | Complete | Floe's data semantics and compiled artifact handoff must remain Floe-owned; OpenChoreo is only plausible as an optional platform-control layer. |
| Recommendation gate | Scored OpenChoreo against Floe architecture and hypotheses. | Adopt candidate for bounded proof | Proof should test optional platform-control integration, not orchestrator replacement. |
| OpenChoreo proof resource generation | Created `docs/research/openchoreo-proof/customer-360-openchoreo.yaml` from `demo/customer-360/floe.yaml` and Floe runtime assumptions. | Complete | Proof includes `Project`, `Component`, `Workload`, `SecretReference`, and `ReleaseBinding`. |
| OpenChoreo render or cluster validation | Preserved Task 6 Helm render evidence, then ran Task 7 YAML structure checks and Kubernetes dry-run commands. | Complete with caveat | Task 6 rendered 3,660 lines across control, data, and observability planes while workflow-plane render failed on missing `argo-workflows`; Task 7 static YAML checks passed, but `kubectl` client/server validation could not reach a Kubernetes API server at `localhost:8080`. |
| Roadmap and ADR evidence | Pending | Pending | Pending |

## Final Outcome

Outcome: In progress

Recommendation: In progress

Confidence: In progress

## Blockers

No blockers recorded at scaffold time.

## Customer 360 Proof Resource Validation

Compilation:

| Command | Result | Notes |
| --- | --- | --- |
| `make compile-demo` | Succeeded | Generated Customer 360 `compiled_artifacts.json` and dbt `target/manifest.json`. The command emitted a non-fatal `ModuleNotFoundError: No module named 'yaml'` from `scripts/resolve-demo-plugins.py` before continuing. |
| `ls demo/customer-360/compiled_artifacts.json demo/customer-360/target/manifest.json` | Succeeded | Both expected files exist. |

Proof validation:

| Command | Result | Notes |
| --- | --- | --- |
| Python YAML structure check | Succeeded | Parsed five YAML documents in order: `Project`, `Component`, `Workload`, `SecretReference`, and `ReleaseBinding`. |
| `kubectl apply --dry-run=client --validate=false -f docs/research/openchoreo-proof/customer-360-openchoreo.yaml` | Not available | `kubectl` attempted API discovery against `http://localhost:8080` and failed with connection refused, so even client dry-run could not recognize the CRDs offline. |
| `kubectl get crd projects.openchoreo.dev components.openchoreo.dev workloads.openchoreo.dev releasebindings.openchoreo.dev secretreferences.openchoreo.dev` | Not available | No Kubernetes API server was reachable at `localhost:8080`; CRD presence could not be checked. |
| `kubectl apply --server-side --dry-run=server -f docs/research/openchoreo-proof/customer-360-openchoreo.yaml` | Not available | Server-side dry-run could not download OpenAPI from `http://localhost:8080/openapi/v2`; OpenChoreo CRD schema validation remains untested. |

Assessment:

The Customer 360 mapping is valid as a static generated-resource proof. Cluster-backed validation remains follow-up work and should be run against an environment with OpenChoreo CRDs installed before treating the resource shape as accepted by OpenChoreo.

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
