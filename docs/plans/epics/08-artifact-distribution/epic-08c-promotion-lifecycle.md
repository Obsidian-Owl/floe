# Epic 8C: Promotion Lifecycle

## Summary

The promotion lifecycle manages artifact progression through environments (dev → staging → prod). It includes promotion gates, approval workflows, rollback capabilities, and audit trails for compliance.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-08c-promotion-lifecycle](https://linear.app/obsidianowl/project/floe-08c-promotion-lifecycle-78acaf0b1d18)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-326 | Environment definitions | CRITICAL |
| REQ-327 | Promotion gates | CRITICAL |
| REQ-328 | Approval workflows | HIGH |
| REQ-329 | Automated promotion | HIGH |
| REQ-330 | Rollback capability | CRITICAL |
| REQ-331 | Promotion history | HIGH |
| REQ-332 | Canary deployments | MEDIUM |
| REQ-333 | Blue-green deployments | MEDIUM |
| REQ-334 | Promotion notifications | MEDIUM |
| REQ-335 | Environment locking | HIGH |
| REQ-336 | Promotion policies | HIGH |
| REQ-337 | Dependency promotion | HIGH |
| REQ-338 | Promotion dry-run | MEDIUM |
| REQ-339 | Audit trail | CRITICAL |

---

## Architecture References

### ADRs
- [ADR-0054](../../../architecture/adr/0054-promotion-workflow.md) - Promotion workflow design
- [ADR-0055](../../../architecture/adr/0055-environment-management.md) - Environment management

### Contracts
- `PromotionManager` - Promotion orchestration
- `PromotionGate` - Gate definition model
- `EnvironmentConfig` - Environment configuration

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── promotion/
│   ├── __init__.py
│   ├── manager.py               # PromotionManager
│   ├── gates.py                 # PromotionGate definitions
│   ├── workflow.py              # Approval workflow
│   ├── rollback.py              # Rollback logic
│   └── history.py               # Promotion history
└── cli/
    └── promote.py               # CLI promote commands
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 3B | Gates check policy validation |
| Blocked By | Epic 8A | Uses OCI client for artifact movement |
| Blocked By | Epic 8B | Verifies signatures before promotion |
| Blocks | Epic 9A | K8s deployment triggered by promotion |

---

## User Stories (for SpecKit)

### US1: Promotion Command (P0)
**As a** data engineer
**I want** to promote artifacts between environments
**So that** I can deploy to staging/production

**Acceptance Criteria**:
- [ ] `floe promote --from dev --to staging` command
- [ ] Artifact copied between registries
- [ ] Promotion gates evaluated
- [ ] Promotion recorded in history

### US2: Promotion Gates (P0)
**As a** platform operator
**I want** gates to block unready promotions
**So that** only validated artifacts reach production

**Acceptance Criteria**:
- [ ] Test pass gate
- [ ] Signature verification gate
- [ ] Policy compliance gate
- [ ] Custom gate support

### US3: Approval Workflows (P1)
**As a** platform operator
**I want** approval required for production
**So that** humans validate before production deployment

**Acceptance Criteria**:
- [ ] Approval request notification
- [ ] Approval via CLI or API
- [ ] Approval timeout handling
- [ ] Approval audit trail

### US4: Rollback (P1)
**As a** platform operator
**I want** to rollback to previous versions
**So that** I can recover from bad deployments

**Acceptance Criteria**:
- [ ] `floe rollback --to <version>` command
- [ ] Previous version re-promoted
- [ ] Rollback reason recorded
- [ ] Notification on rollback

### US5: Promotion History (P2)
**As a** compliance officer
**I want** complete promotion history
**So that** I can audit all deployments

**Acceptance Criteria**:
- [ ] All promotions logged
- [ ] Who, what, when, why recorded
- [ ] Gate results stored
- [ ] Exportable audit reports

---

## Technical Notes

### Key Decisions
- Environments defined in manifest.yaml
- Promotion = tag in destination registry (not copy)
- Gates are synchronous (block until pass/fail)
- Rollback is promotion of previous version

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Gate timeout | MEDIUM | MEDIUM | Configurable timeout, manual override |
| Approval bottleneck | MEDIUM | HIGH | Auto-approval for non-prod |
| Rollback complexity | MEDIUM | HIGH | Clear rollback procedures |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_promotion.py`
- **Integration**: `packages/floe-core/tests/integration/test_promotion_workflow.py`
- **E2E**: `tests/e2e/test_promotion_flow.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/04-artifact-distribution/`
- `docs/architecture/distribution/`
- `packages/floe-core/src/floe_core/promotion/`

### Related Existing Code
- OCIClient from Epic 8A
- SigningClient from Epic 8B
- Policy validation from Epic 3B

### External Dependencies
- None (uses internal components)
