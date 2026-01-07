# Epic 7C: Network & Pod Security

## Summary

Network and pod security implements defense-in-depth for the floe platform. This includes NetworkPolicies for traffic control, Pod Security Standards enforcement, and security context configuration for all workloads.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-07c-network-pod-security](https://linear.app/obsidianowl/project/floe-07c-network-pod-security-900c829e6300)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-441 | NetworkPolicy templates | CRITICAL |
| REQ-442 | Ingress rules | HIGH |
| REQ-443 | Egress rules | HIGH |
| REQ-444 | Default deny policy | CRITICAL |
| REQ-445 | Service mesh integration | MEDIUM |
| REQ-446 | mTLS configuration | HIGH |
| REQ-447 | Pod Security Standards | CRITICAL |
| REQ-448 | Security context defaults | HIGH |
| REQ-449 | Read-only root filesystem | HIGH |
| REQ-450 | Non-root execution | CRITICAL |
| REQ-451 | Capability dropping | HIGH |
| REQ-452 | Seccomp profiles | MEDIUM |
| REQ-453 | AppArmor/SELinux profiles | LOW |
| REQ-454 | Resource limits | HIGH |
| REQ-455 | Priority classes | MEDIUM |
| REQ-456 | Pod disruption budgets | MEDIUM |
| REQ-457 | Anti-affinity rules | MEDIUM |
| REQ-458 | Topology spread constraints | MEDIUM |
| REQ-459 | Image pull policies | HIGH |
| REQ-460 | Image scanning integration | HIGH |
| REQ-461 | Runtime security monitoring | MEDIUM |
| REQ-462 | Network segmentation | HIGH |
| REQ-463 | External traffic control | HIGH |
| REQ-464 | DNS policy | MEDIUM |
| REQ-465 | Service account token mounting | HIGH |
| REQ-466 | Secret volume mounts | HIGH |
| REQ-467 | Pod security admission | CRITICAL |

---

## Architecture References

### ADRs
- [ADR-0042](../../../architecture/adr/0042-network-security.md) - Network security architecture
- [ADR-0043](../../../architecture/adr/0043-pod-security.md) - Pod security standards

### Contracts
- `NetworkPolicyTemplate` - Network policy generation
- `SecurityContextConfig` - Pod security context
- `PodSecurityProfile` - PSS profile configuration

---

## File Ownership (Exclusive)

```text
charts/floe-platform/
├── templates/
│   ├── network/
│   │   ├── default-deny.yaml
│   │   ├── ingress-rules.yaml
│   │   ├── egress-rules.yaml
│   │   └── inter-service.yaml
│   └── security/
│       ├── pod-security.yaml
│       └── _security-context.tpl
└── values/
    └── security-defaults.yaml
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 7B | Uses RBAC for authorization |
| Blocks | Epic 9A | K8s deployment uses security policies |
| Blocks | Epic 9B | Helm charts include security config |

---

## User Stories (for SpecKit)

### US1: Default Deny NetworkPolicy (P0)
**As a** security engineer
**I want** default deny network policies
**So that** only explicitly allowed traffic flows

**Acceptance Criteria**:
- [ ] Default deny ingress in all namespaces
- [ ] Default deny egress in all namespaces
- [ ] Explicit allow for required services
- [ ] DNS egress always allowed

### US2: Pod Security Standards (P0)
**As a** security engineer
**I want** PSS enforcement
**So that** pods follow security best practices

**Acceptance Criteria**:
- [ ] Baseline profile for all namespaces
- [ ] Restricted profile for production
- [ ] Privileged only for system namespaces
- [ ] Violation alerts configured

### US3: Security Context Defaults (P1)
**As a** platform operator
**I want** secure defaults for all pods
**So that** workloads are hardened automatically

**Acceptance Criteria**:
- [ ] Non-root user by default
- [ ] Read-only root filesystem
- [ ] All capabilities dropped
- [ ] Seccomp profile applied

### US4: Network Segmentation (P1)
**As a** security engineer
**I want** data products network-isolated
**So that** compromises are contained

**Acceptance Criteria**:
- [ ] Data product namespaces isolated
- [ ] Platform services accessible to all
- [ ] External egress controlled
- [ ] Cross-namespace rules explicit

### US5: mTLS Configuration (P2)
**As a** security engineer
**I want** mTLS between services
**So that** traffic is encrypted and authenticated

**Acceptance Criteria**:
- [ ] Service mesh integration (Istio/Linkerd)
- [ ] Automatic certificate rotation
- [ ] Strict mTLS mode
- [ ] Certificate validation

---

## Technical Notes

### Key Decisions
- Default deny is mandatory for all namespaces
- Pod Security Standards "restricted" for production
- Resource limits required on all containers
- Image scanning in CI pipeline, not admission

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Policy breaks workloads | HIGH | HIGH | Dry-run mode, gradual rollout |
| Performance overhead (mTLS) | MEDIUM | MEDIUM | Sidecar optimization |
| NetworkPolicy gaps | MEDIUM | HIGH | Policy testing, audit |

### Test Strategy
- **Unit**: Policy YAML validation
- **Integration**: `charts/floe-platform/tests/integration/test_network_policy.py`
- **E2E**: Network connectivity tests in Kind

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/05-security-access-control/`
- `docs/architecture/security/`
- `charts/floe-platform/templates/network/`
- `charts/floe-platform/templates/security/`

### Related Existing Code
- RBAC from Epic 7B
- Helm charts from Epic 9B

### External Dependencies
- Kubernetes NetworkPolicy API
- Pod Security Admission (K8s 1.25+)
- Optional: Istio/Linkerd for mTLS
