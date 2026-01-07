# Epic 7B: Kubernetes RBAC

## Summary

Kubernetes RBAC integration provides role-based access control for floe platform components. This includes ServiceAccount management, Role/RoleBinding creation, and integration with external identity providers for user authentication.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-07b-k8s-rbac](https://linear.app/obsidianowl/project/floe-07b-k8s-rbac-f6aa70e4c792)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-425 | ServiceAccount generation | CRITICAL |
| REQ-426 | Role definition templates | HIGH |
| REQ-427 | RoleBinding management | HIGH |
| REQ-428 | ClusterRole for platform components | HIGH |
| REQ-429 | Namespace isolation | CRITICAL |
| REQ-430 | Least privilege enforcement | CRITICAL |
| REQ-431 | RBAC audit logging | HIGH |
| REQ-432 | Role aggregation | MEDIUM |
| REQ-433 | Dynamic role updates | MEDIUM |
| REQ-434 | RBAC validation | HIGH |
| REQ-435 | Permission debugging tools | MEDIUM |
| REQ-436 | OIDC group mapping | HIGH |
| REQ-437 | ServiceAccount tokens | HIGH |
| REQ-438 | Token audience validation | HIGH |
| REQ-439 | Pod security context | HIGH |
| REQ-440 | Workload identity | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0041](../../../architecture/adr/0041-k8s-rbac.md) - Kubernetes RBAC strategy
- [ADR-0040](../../../architecture/adr/0040-identity-architecture.md) - Identity architecture

### Contracts
- `RBACManager` - RBAC management interface
- `RoleTemplate` - Role definition template
- `ServiceAccountConfig` - SA configuration model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── security/
│   └── rbac.py                  # RBAC utilities

charts/floe-platform/
├── templates/
│   ├── rbac/
│   │   ├── serviceaccount.yaml
│   │   ├── role.yaml
│   │   ├── rolebinding.yaml
│   │   ├── clusterrole.yaml
│   │   └── clusterrolebinding.yaml
│   └── _rbac-helpers.tpl
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 7A | Uses identity for authentication |
| Blocks | Epic 7C | Network policies use RBAC context |
| Blocks | Epic 9A | K8s deployment requires RBAC |
| Blocks | Epic 9B | Helm charts include RBAC templates |

---

## User Stories (for SpecKit)

### US1: ServiceAccount Generation (P0)
**As a** platform operator
**I want** ServiceAccounts created automatically
**So that** workloads have proper identities

**Acceptance Criteria**:
- [ ] SA per data product
- [ ] SA for platform services
- [ ] Token projection configured
- [ ] Annotation for external identity

### US2: Role Templates (P0)
**As a** platform operator
**I want** predefined roles for common patterns
**So that** I don't reinvent RBAC for each deployment

**Acceptance Criteria**:
- [ ] `floe-data-engineer` role template
- [ ] `floe-platform-admin` role template
- [ ] `floe-viewer` role template
- [ ] Custom role extension support

### US3: Namespace Isolation (P0)
**As a** security engineer
**I want** data products isolated by namespace
**So that** workloads can't access other products' resources

**Acceptance Criteria**:
- [ ] One namespace per data product
- [ ] Cross-namespace access denied by default
- [ ] Explicit allowlist for shared resources
- [ ] Network policy enforcement

### US4: OIDC Group Mapping (P1)
**As a** platform operator
**I want** OIDC groups mapped to K8s roles
**So that** corporate groups control K8s access

**Acceptance Criteria**:
- [ ] Group claim extraction
- [ ] RoleBinding from group membership
- [ ] Automatic binding updates
- [ ] Group sync verification

### US5: Least Privilege Enforcement (P1)
**As a** security engineer
**I want** minimum required permissions
**So that** blast radius is limited

**Acceptance Criteria**:
- [ ] No cluster-admin for workloads
- [ ] Namespace-scoped roles preferred
- [ ] Permission audit tooling
- [ ] Policy enforcement (OPA Gatekeeper)

---

## Technical Notes

### Key Decisions
- One ServiceAccount per data product
- Namespace isolation is mandatory
- ClusterRoles only for platform components
- OIDC integration via Kubernetes API server config

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Permission escalation | MEDIUM | CRITICAL | OPA policies, audit |
| SA token exposure | MEDIUM | HIGH | Projected tokens, short TTL |
| Role sprawl | HIGH | MEDIUM | Role aggregation, templates |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_rbac.py`
- **Integration**: `charts/floe-platform/tests/integration/test_rbac.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/05-security-access-control/`
- `docs/architecture/security/`
- `charts/floe-platform/templates/rbac/`

### Related Existing Code
- Identity plugin from Epic 7A

### External Dependencies
- `kubernetes>=26.0.0`
