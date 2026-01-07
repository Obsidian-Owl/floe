# Epic 9A: K8s Deployment

## Summary

Kubernetes deployment provides the runtime platform for floe data products. This includes deployment controllers, service configuration, resource management, and integration with the floe CLI for deploy operations.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-09a-k8s-deployment](https://linear.app/obsidianowl/project/floe-09a-k8s-deployment-ac56ffa47013)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-600 | Deployment controller | CRITICAL |
| REQ-601 | Namespace management | HIGH |
| REQ-602 | ConfigMap generation | HIGH |
| REQ-603 | Secret mounting | CRITICAL |
| REQ-604 | Service creation | HIGH |
| REQ-605 | Ingress configuration | MEDIUM |
| REQ-606 | Resource quotas | HIGH |
| REQ-607 | Limit ranges | HIGH |
| REQ-608 | HPA configuration | MEDIUM |
| REQ-609 | PDB configuration | MEDIUM |
| REQ-610 | Node affinity | MEDIUM |
| REQ-611 | Tolerations | MEDIUM |
| REQ-612 | Volume management | HIGH |
| REQ-613 | Init containers | HIGH |
| REQ-614 | Sidecar configuration | MEDIUM |
| REQ-615 | Health probes | CRITICAL |
| REQ-616 | Deployment status tracking | HIGH |
| REQ-617 | Rollout management | HIGH |
| REQ-618 | Deployment history | HIGH |
| REQ-619 | Kubectl integration | HIGH |
| REQ-620 | Multi-cluster support | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0060](../../../architecture/adr/0060-k8s-deployment.md) - Kubernetes deployment architecture
- [ADR-0061](../../../architecture/adr/0061-workload-types.md) - Workload type selection

### Contracts
- `DeploymentController` - Deployment orchestration
- `WorkloadConfig` - Workload configuration model
- `DeploymentStatus` - Status tracking model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── deployment/
│   ├── __init__.py
│   ├── controller.py            # DeploymentController
│   ├── workloads.py             # Workload generation
│   ├── resources.py             # Resource configuration
│   ├── status.py                # Status tracking
│   └── rollout.py               # Rollout management
└── cli/
    └── deploy.py                # CLI deploy commands
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 4A-D | Deploys plugin workloads |
| Blocked By | Epic 7B | Uses RBAC for authorization |
| Blocked By | Epic 7C | Uses network/pod security |
| Blocked By | Epic 8A | Pulls artifacts from registry |
| Blocked By | Epic 8B | Verifies artifact signatures |
| Blocks | Epic 9B | Helm charts wrap deployment logic |

---

## User Stories (for SpecKit)

### US1: Deploy Command (P0)
**As a** data engineer
**I want** to deploy data products to Kubernetes
**So that** my pipelines run in the cluster

**Acceptance Criteria**:
- [ ] `floe deploy` command works
- [ ] Deployment from OCI artifact
- [ ] Namespace created if needed
- [ ] Status reported during deployment

### US2: Resource Configuration (P0)
**As a** platform operator
**I want** resources configured per workload
**So that** workloads have appropriate limits

**Acceptance Criteria**:
- [ ] CPU/memory requests and limits
- [ ] Resource quotas per namespace
- [ ] LimitRange defaults
- [ ] Resource validation at deploy time

### US3: Health Probes (P1)
**As a** platform operator
**I want** health probes configured
**So that** unhealthy pods are restarted

**Acceptance Criteria**:
- [ ] Liveness probe for all containers
- [ ] Readiness probe for services
- [ ] Startup probe for slow starts
- [ ] Configurable probe parameters

### US4: Deployment Status (P1)
**As a** data engineer
**I want** deployment status tracked
**So that** I know when deployment is complete

**Acceptance Criteria**:
- [ ] Real-time status updates
- [ ] Pod readiness tracking
- [ ] Error reporting for failures
- [ ] Rollout progress percentage

### US5: Rollout Management (P2)
**As a** platform operator
**I want** controlled rollouts
**So that** deployments are safe

**Acceptance Criteria**:
- [ ] Rolling update strategy
- [ ] Rollout pause/resume
- [ ] Rollout undo
- [ ] Surge and max unavailable config

---

## Technical Notes

### Key Decisions
- Deployments used for stateless workloads
- StatefulSets for Dagster daemon
- Jobs for dbt runs
- CronJobs for scheduled pipelines

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Resource exhaustion | MEDIUM | HIGH | Quotas, limits, monitoring |
| Deployment failures | MEDIUM | HIGH | Health probes, rollback |
| Multi-cluster complexity | HIGH | MEDIUM | Single cluster first |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_deployment.py`
- **Integration**: `packages/floe-core/tests/integration/test_k8s_deploy.py`
- **E2E**: `tests/e2e/test_deployment_flow.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/07-deployment-operations/`
- `docs/architecture/deployment/`
- `packages/floe-core/src/floe_core/deployment/`

### Related Existing Code
- Plugin configurations from Epic 4A-D
- RBAC from Epic 7B
- OCIClient from Epic 8A

### External Dependencies
- `kubernetes>=26.0.0`
