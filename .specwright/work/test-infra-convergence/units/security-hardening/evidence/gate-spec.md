# Gate: Spec Compliance

**Status**: PASS

## Acceptance Criteria → Evidence Map

| AC | Description | Evidence | Status |
|----|-------------|----------|--------|
| AC-1 | Dagster subchart PSS security contexts | `tests/unit/test_dagster_security_contexts.py` (8 tests) | PASS |
| AC-2 | OTel + Jaeger PSS contexts (Jaeger preserves UID 10001) | `tests/unit/test_observability_security_contexts.py` (3 tests) | PASS |
| AC-3 | MinIO Bitnami enabled+hardened context | `tests/unit/test_observability_security_contexts.py` (2 tests) | PASS |
| AC-4 | Helm-template contract test for security contexts | `tests/contract/test_helm_security_contexts.py` (3 tests) | PASS |
| AC-5 | Containerized kubeconform (pinned image) | `tests/unit/test_makefile_containerized_tools.py::test_helm_validate_uses_containerized_kubeconform` | PASS |
| AC-6 | Containerized kubesec (pinned image) | `tests/unit/test_makefile_containerized_tools.py::test_helm_security_uses_containerized_kubesec` | PASS |
| AC-7 | Containerized helm-unittest (pinned image, no host plugin) | `tests/unit/test_makefile_containerized_tools.py::test_helm_test_unit_uses_containerized_helm_unittest` | PASS |
| AC-8 | Standard runner: no list/watch on secrets, get retained | `tests/contract/test_rbac_least_privilege.py` (2 tests) | PASS |
| AC-9 | Destructive runner: update/delete scoped via resourceNames | `tests/contract/test_rbac_least_privilege.py` (2 tests) | PASS |
| AC-10 | AUDIT.md documents Marquez root-user gap with SEC-001 ID | `tests/unit/test_audit_marquez_gap.py` (2 tests) | PASS |

## Deviations / Deficiencies

None blocking. Documented WARNs:

1. **MinIO Bitnami schema gap (AC-3)**: Bitnami's MinIO chart does not
   support nested `capabilities.drop` on its container security context.
   The spec acknowledges this gap (`enabled: true` + `runAsNonRoot`
   + `allowPrivilegeEscalation: false` are the available hardening knobs).
   Implemented and tested per spec.

2. **Jaeger UID preservation (AC-2)**: Upstream Jaeger all-in-one image
   requires UID 10001 and cannot reuse the shared PSS anchor (which pins
   UID 1000). Spec explicitly allowed an inline context. Implemented
   with matching UID at both pod and container level.

3. **Marquez exemption (AC-10)**: Documented as accepted gap SEC-001 in
   `.specwright/AUDIT.md`, linked to upstream MarquezProject/marquez#3060.
   The contract test `test_helm_security_contexts.py` explicitly excludes
   Marquez pods via `MARQUEZ_NAME_MARKERS`.

4. **PostgreSQL init container removal (side effect, not in spec)**:
   Hardening the PostgreSQL StatefulSet pod-level context required removing
   a pre-existing root `init-permissions` init container that had no PSS
   hardening of its own. PVC ownership is now handled by `fsGroup: 1000`
   via kubelet. For upgrades of existing clusters with mis-owned PVCs,
   a manual chown may be required. Flagged to user.
