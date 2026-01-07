# Epic 3B: Policy Validation

## Summary

Policy validation implements specific validation rules for platform configurations. This includes schema validation, naming conventions, resource limits, security policies, and compliance checks that run through the PolicyEnforcer.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-03b-policy-validation](https://linear.app/obsidianowl/project/floe-03b-policy-validation-388fcbc3817f)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-215 | Schema validation rules | CRITICAL |
| REQ-216 | Naming convention enforcement | HIGH |
| REQ-217 | Resource limit validation | HIGH |
| REQ-218 | Security policy rules | CRITICAL |
| REQ-219 | Compliance rule framework | HIGH |
| REQ-220 | Custom rule definitions | MEDIUM |
| REQ-221 | Rule priority/ordering | MEDIUM |
| REQ-222 | Conditional rule execution | MEDIUM |
| REQ-223 | Rule documentation generation | LOW |
| REQ-224 | Compliance reporting | HIGH |
| REQ-225 | Rule violation severity levels | HIGH |
| REQ-226 | Auto-remediation suggestions | MEDIUM |
| REQ-227 | Rule exceptions/overrides | HIGH |
| REQ-228 | Rule testing utilities | HIGH |
| REQ-229 | Rule performance metrics | LOW |
| REQ-230 | Batch validation support | MEDIUM |
| REQ-231 | Incremental validation | LOW |
| REQ-232 | Validation result caching | MEDIUM |
| REQ-233 | Rule dependency resolution | MEDIUM |
| REQ-234 | Cross-resource validation | HIGH |
| REQ-235 | Validation API | HIGH |

---

## Architecture References

### ADRs
- [ADR-0020](../../../architecture/adr/0020-policy-enforcement.md) - Policy enforcement architecture
- [ADR-0022](../../../architecture/adr/0022-validation-rules.md) - Validation rule patterns

### Contracts
- `ValidationRule` - Base rule interface
- `ValidationResult` - Rule evaluation result
- `ComplianceReport` - Aggregated compliance status

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── policy/
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── base.py              # ValidationRule base
│   │   ├── schema.py            # Schema validation rules
│   │   ├── naming.py            # Naming convention rules
│   │   ├── security.py          # Security policy rules
│   │   ├── resources.py         # Resource limit rules
│   │   └── compliance.py        # Compliance rules
│   ├── report.py                # ComplianceReport model
│   └── registry.py              # Rule registry
└── cli/
    └── validate.py              # CLI validate command
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 3A | Uses PolicyEnforcer engine |
| Blocks | Epic 3C | Data contracts include validation |
| Blocks | Epic 8C | Promotion requires validation pass |

---

## User Stories (for SpecKit)

### US1: Schema Validation Rules (P0)
**As a** platform operator
**I want** automatic schema validation
**So that** configurations are always structurally correct

**Acceptance Criteria**:
- [ ] Required fields enforced
- [ ] Type validation for all fields
- [ ] Nested structure validation
- [ ] Custom validation messages

### US2: Security Policy Rules (P0)
**As a** security engineer
**I want** security policies enforced automatically
**So that** insecure configurations are rejected

**Acceptance Criteria**:
- [ ] No plaintext secrets allowed
- [ ] Minimum TLS version enforced
- [ ] Network policy requirements checked
- [ ] RBAC constraints validated

### US3: Compliance Reporting (P1)
**As a** compliance officer
**I want** compliance reports generated automatically
**So that** I can demonstrate governance adherence

**Acceptance Criteria**:
- [ ] `floe compliance report` command works
- [ ] JSON/HTML report formats
- [ ] Historical comparison support
- [ ] Integration with CI/CD pipelines

### US4: Custom Rule Definitions (P2)
**As a** platform operator
**I want** to define custom validation rules
**So that** I can enforce organization-specific policies

**Acceptance Criteria**:
- [ ] YAML-based rule definitions
- [ ] Python-based rule plugins
- [ ] Rule testing framework
- [ ] Rule documentation generation

---

## Technical Notes

### Key Decisions
- Rules are stateless functions (no side effects)
- Rule ordering determined by dependency graph
- Severity levels: ERROR (blocks), WARNING (alerts), INFO (advisory)
- All rules registered in central registry

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rule conflicts | MEDIUM | MEDIUM | Clear precedence rules |
| Performance with many rules | MEDIUM | MEDIUM | Lazy evaluation, caching |
| False positives | MEDIUM | HIGH | Comprehensive test suites |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_validation_rules.py`
- **Contract**: `tests/contract/test_validation_contract.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/03-data-governance/`
- `packages/floe-core/src/floe_core/policy/`

### Related Existing Code
- Epic 3A PolicyEnforcer

### External Dependencies
- `pydantic>=2.0`
- `jsonschema>=4.0` (JSON Schema validation)
