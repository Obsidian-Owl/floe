# Epic 3A: Policy Enforcer Core

## Summary

The PolicyEnforcer is a core component that validates platform configurations against defined policies. It provides an extensible policy evaluation engine with hooks for enforcement at compile-time and runtime, preparing for future OPA integration.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-03a-policy-enforcer](https://linear.app/obsidianowl/project/floe-03a-policy-enforcer-08a4f4df013c)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-200 | PolicyEnforcer ABC | CRITICAL |
| REQ-201 | Policy definition schema | HIGH |
| REQ-202 | Policy evaluation engine | CRITICAL |
| REQ-203 | OPA integration preparation | HIGH |
| REQ-204 | Policy context injection | HIGH |
| REQ-205 | Enforcement hooks | HIGH |
| REQ-206 | Policy caching | MEDIUM |
| REQ-207 | Policy versioning | MEDIUM |
| REQ-208 | Audit logging | HIGH |
| REQ-209 | Policy testing framework | HIGH |
| REQ-210 | Dry-run mode | MEDIUM |
| REQ-211 | Policy inheritance | MEDIUM |
| REQ-212 | Default policies | HIGH |
| REQ-213 | Policy override rules | MEDIUM |
| REQ-214 | Policy documentation | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0020](../../../architecture/adr/0020-policy-enforcement.md) - Policy enforcement architecture
- [ADR-0021](../../../architecture/adr/0021-opa-integration.md) - OPA integration strategy

### Contracts
- `PolicyEnforcer` - Core policy evaluation ABC
- `PolicyResult` - Evaluation result model
- `PolicyContext` - Context for policy evaluation

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── policy/
│   ├── __init__.py
│   ├── enforcer.py              # PolicyEnforcer ABC
│   ├── context.py               # PolicyContext model
│   ├── result.py                # PolicyResult model
│   ├── schema.py                # Policy definition schema
│   ├── cache.py                 # Policy caching
│   └── hooks.py                 # Enforcement hooks
└── cli/
    └── policy.py                # CLI policy commands
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 2A | Policies defined in manifest |
| Blocked By | Epic 2B | Validates CompiledArtifacts |
| Blocks | Epic 3B | Policy validation uses enforcer |
| Blocks | Epic 3C | Data contracts use policy engine |

---

## User Stories (for SpecKit)

### US1: Policy Evaluation Engine (P0)
**As a** platform operator
**I want** to define and evaluate policies against configurations
**So that** governance standards are enforced automatically

**Acceptance Criteria**:
- [ ] `PolicyEnforcer.evaluate(context)` returns PolicyResult
- [ ] Multiple policies evaluated in single pass
- [ ] Policy failures include actionable error messages
- [ ] Dry-run mode shows what would be enforced

### US2: Enforcement Hooks (P1)
**As a** platform developer
**I want** hooks to enforce policies at key points
**So that** policies are checked at compile-time and runtime

**Acceptance Criteria**:
- [ ] Pre-compile hook validates FloeSpec
- [ ] Post-compile hook validates CompiledArtifacts
- [ ] Runtime hooks for deployment validation
- [ ] Hook failures block operations by default

### US3: Policy Testing Framework (P1)
**As a** platform operator
**I want** to test policies before deploying them
**So that** I can validate policy logic safely

**Acceptance Criteria**:
- [ ] `floe policy test` command works
- [ ] Test fixtures for common scenarios
- [ ] Coverage reporting for policy rules
- [ ] CI integration guidance documented

### US4: Audit Logging (P2)
**As a** compliance officer
**I want** policy evaluations logged with full context
**So that** I can audit governance enforcement

**Acceptance Criteria**:
- [ ] All evaluations logged with timestamp
- [ ] Policy version recorded in logs
- [ ] Context (who, what, when) captured
- [ ] Integration with OpenTelemetry traces

---

## Technical Notes

### Key Decisions
- Policy engine is synchronous (no async evaluation)
- OPA integration via subprocess/HTTP (not embedded)
- Policies versioned independently from floe version
- Default policies included in floe-core package

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Policy evaluation performance | MEDIUM | HIGH | Caching, lazy loading |
| OPA dependency complexity | MEDIUM | MEDIUM | Abstract via PolicyEnforcer ABC |
| Policy version drift | LOW | HIGH | Version validation at load time |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_policy_enforcer.py`
- **Contract**: `tests/contract/test_policy_contract.py`
- **Integration**: Policy evaluation with real OPA (when integrated)

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/03-data-governance/`
- `docs/architecture/enforcement/`
- `packages/floe-core/`

### Related Existing Code
- None (greenfield)

### External Dependencies
- `pydantic>=2.0` (policy schema)
- Future: `opa` (policy evaluation)
