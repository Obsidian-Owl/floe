# Spec: Security Hardening + Containerized Tools

## Acceptance Criteria

### AC-1: Security context propagation to Dagster subchart

`values.yaml` MUST use YAML anchors to define security contexts once and propagate
them to the core Dagster components:

- `dagster.dagsterWebserver.podSecurityContext` and `.securityContext`
- `dagster.dagsterDaemon.podSecurityContext` and `.securityContext`
- `dagster.runLauncher.config.k8sRunLauncher.runK8sConfig.podSpecConfig.securityContext`
  and `.runK8sConfig.containerConfig.securityContext` (raw K8s — the Dagster subchart
  schema routes run-pod security through `runK8sConfig`, not top-level keys on
  `k8sRunLauncher`)

After rendering with `helm template`, every Dagster pod spec above MUST contain:
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: ["ALL"]`

**Out of scope (deferred)**: `dagster-user-deployments` (the dashed-key Dagster
subchart dependency) is NOT covered by AC-1 because base `values.yaml` leaves
`deployments: []` empty — actual deployments are populated by overlay files
(`values-*.yaml`). Overlay deployment coverage is tracked separately.

### AC-2: Security context propagation to OTel and Jaeger subcharts

- `opentelemetry-collector.podSecurityContext` and `.securityContext` MUST be set.
- `jaeger.allInOne.securityContext` MUST include `allowPrivilegeEscalation: false`
  and `capabilities.drop: ["ALL"]`. Jaeger's existing `runAsUser: 10001` MUST be preserved.

After rendering, OTel collector and Jaeger pods MUST have `runAsNonRoot: true` and
`capabilities.drop: ["ALL"]`.

### AC-3: Security context propagation to MinIO subchart

MinIO uses Bitnami schema. `values.yaml` MUST set:

```yaml
minio:
  podSecurityContext:
    enabled: true
    fsGroup: 1000
  containerSecurityContext:
    enabled: true
    runAsNonRoot: true
    runAsUser: 1000
    allowPrivilegeEscalation: false
```

**Note**: MinIO Bitnami chart does NOT support `capabilities.drop` in the standard
`containerSecurityContext`. If the chart doesn't render it, document as known gap
(lower risk than Dagster/OTel since MinIO is internal storage only).

### AC-4: Contract test for security context validation

A new contract test MUST render the Helm chart with `helm template` and assert that
ALL pod specs (except Marquez) contain:

- `spec.securityContext.runAsNonRoot: true`
- `spec.containers[*].securityContext.allowPrivilegeEscalation: false`

The test MUST explicitly exclude Marquez pods (known exception per D-6).
The test MUST fail if a new subchart is added without security context propagation.

Location: `tests/contract/test_helm_security_contexts.py`

**Boundary conditions**:
- Init containers MUST also have security contexts.
- Sidecar containers (if any) MUST also have security contexts.
- The test MUST parse multi-document YAML output from `helm template`.

### AC-5: Containerized kubeconform

`make helm-validate` MUST run kubeconform via Docker container, not host binary:

```bash
docker run --rm -v $(PWD)/charts:/charts ghcr.io/yannh/kubeconform:v0.6.7 ...
```

Image version MUST be pinned (not `:latest`). The target MUST work without kubeconform
installed on the host.

### AC-6: Containerized kubesec

`make helm-security` MUST run kubesec via Docker container:

```bash
docker run --rm -v $(PWD)/charts:/charts kubesec/kubesec:v2.14.1 scan ...
```

Image version MUST be pinned. The target MUST work without kubesec on the host.

### AC-7: Containerized helm-unittest

`make helm-test-unit` MUST run helm-unittest via Docker container:

```bash
docker run --rm -v $(PWD)/charts:/charts helmunittest/helm-unittest:3.16.1 ...
```

Image version MUST be pinned. The target MUST work without helm-unittest plugin on host.
Existing `make helm-test` (live cluster tests) is unchanged.

### AC-8: RBAC least-privilege for standard test runner

The standard test runner Role (`testing/k8s/rbac/e2e-test-runner.yaml`) MUST restrict
secrets access to least-privilege:

- Remove `list` and `watch` verbs — only `get` is needed for Helm release state queries.
- Add `resourceNames` constraint scoping access to known secret patterns (e.g.,
  `sh.helm.release.*`) if the API group supports it, OR document why broad `get` is
  acceptable.

A contract test MUST render the RBAC manifest and assert:
- Secrets rule does NOT include `list` or `watch` verbs.
- The test MUST fail if secrets verbs are re-expanded.

Location: `tests/contract/test_rbac_least_privilege.py`

### AC-9: RBAC least-privilege for destructive test runner

The destructive test runner Role (`testing/k8s/rbac/e2e-destructive-runner.yaml`) MUST
restrict secrets CRUD to only the secrets Helm actually needs:

- Add `resourceNames` constraint scoping `create`/`update`/`delete` to Helm release
  secret patterns (prefix `sh.helm.release.v1.`).
- If `resourceNames` cannot be used with `create` (K8s limitation), document the gap
  and constrain `update`/`delete` at minimum.

A contract test MUST assert:
- Secrets rule includes `resourceNames` for `update` and `delete` verbs.
- The test MUST fail if unrestricted secrets CRUD is reintroduced.

Location: `tests/contract/test_rbac_least_privilege.py`

### AC-10: Marquez gap documentation

`AUDIT.md` MUST document the Marquez root-user gap:

- Finding: Marquez container runs as root (UID 0).
- Upstream: GitHub issue #3060, no fix timeline.
- Risk: PSS restricted profile cannot be enforced namespace-wide while Marquez is present.
- Mitigation: Accept for now. Separate namespace for Marquez is a future work unit.
